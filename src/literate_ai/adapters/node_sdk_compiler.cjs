'use strict';
// Framework-owned compiler host: project and compiler inputs are immutable bytes.
const path = require('node:path');
const vm = require('node:vm');
const {builtinModules} = require('node:module');
const compilerRoot = '/__literate_compiler__';
const virtualRoot = '/__literate_sdk__';
const canonical = value => path.posix.resolve(value.replaceAll('\\', '/'));
const own = (value, keys) => value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join('|') === keys.sort().join('|');
function relative(value) {
  if (typeof value !== 'string' || !value || value.length > 512 || value.normalize('NFC') !== value || value.includes('\\') || value.startsWith('/') || value.includes(':') || /[%#?<>\"|*\x00-\x1f]/.test(value) || value.split('/').some(part => !part || part === '.' || part === '..' || /[ .]$/.test(part) || /^(con|prn|aux|nul|conin\$|conout\$|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)/i.test(part))) throw Error('invalid relative compiler path');
  return value;
}

function inventory(rows, maximum, byteLimit) {
  if (!Array.isArray(rows) || !rows.length || rows.length > maximum) throw Error('compiler inventory bound');
  const files = new Map(), prefixes = new Map(); let total = 0;
  for (const row of rows) {
    if (!own(row, ['path', 'content']) || typeof row.content !== 'string') throw Error('compiler file shape');
    const name = relative(row.path), content = Buffer.from(row.content, 'base64');
    if (content.toString('base64') !== row.content || content.length > 16 * 1024 * 1024 || (total += content.length) > byteLimit) throw Error('compiler content bound');
    const parts = name.split('/');
    for (let depth=1; depth<=parts.length; depth++) {
      const prefix=parts.slice(0,depth).join('/'), alias=prefix.toUpperCase().toLowerCase().normalize('NFC');
      if (prefixes.has(alias) && prefixes.get(alias) !== prefix) throw Error('compiler path alias');
      prefixes.set(alias,prefix);
    }
    if (files.has(name)) throw Error('duplicate compiler file');
    files.set(name, content);
  }
  for (const name of files.keys()) {
    const parts=name.split('/');
    for(let depth=1;depth<parts.length;depth++) if(files.has(parts.slice(0,depth).join('/'))) throw Error('compiler file ancestor');
  }
  return files;
}
function loadCompiler(snapshot) {
  const cache = new Map(), builtins = new Set(builtinModules.flatMap(name => [name, 'node:'+name]));
  function load(name) {
    if (cache.has(name)) return cache.get(name).exports;
    const bytes=snapshot.get(name);
    if (!bytes) throw Error('compiler dependency absent from selected snapshot');
    const module={exports:{}}; cache.set(name,module);
    if (name.endsWith('.json')) {module.exports=JSON.parse(bytes.toString('utf8'));return module.exports;}
    if (!name.endsWith('.js')) throw Error('unsupported compiler dependency');
    const localRequire = specifier => {
      if (builtins.has(specifier)) return require(specifier);
      if (!specifier.startsWith('.')) throw Error('compiler dependency leaves selected snapshot');
      const resolved=path.posix.normalize(path.posix.join(path.posix.dirname(name),specifier));
      for (const candidate of [resolved,resolved+'.js',resolved+'.json',resolved+'/index.js']) if(snapshot.has(candidate)) return load(candidate);
      throw Error('compiler dependency absent from selected snapshot');
    };
    const filename=compilerRoot+'/'+name;
    // Compile exactly the verified packet bytes; never require the SDK from disk.
    const wrapper=vm.runInThisContext('(function(exports,require,module,__filename,__dirname){'+bytes.toString('utf8')+'\n})',{filename});
    wrapper(module.exports,localRequire,module,filename,path.posix.dirname(filename));
    return module.exports;
  }
  return load('lib/typescript.js');
}
(async () => {
  const chunks=[];let bytes=0;
  for await(const chunk of process.stdin) {
    if((bytes+=chunk.length)>64*1024*1024) throw Error('compiler input bound');
    chunks.push(chunk);
  }
  const request=JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (!own(request,['version','operation','files','roots','compiler_files']) || request.version!==1 || !['compile','check'].includes(request.operation) || !Array.isArray(request.roots) || !request.roots.length || request.roots.length>1024) throw Error('compiler request shape');
  const source=inventory(request.files,4096,32*1024*1024);
  const snapshot=inventory(request.compiler_files,1024,32*1024*1024);
  const files=new Map([...source].map(([name,bytes])=>[virtualRoot+'/'+name,bytes.toString('utf8')]));
  const toolFiles=new Map([...snapshot].map(([name,bytes])=>[compilerRoot+'/'+name,bytes.toString('utf8')]));
  const ts=loadCompiler(snapshot);
  const all = new Map([...files, ...toolFiles]);
  const directories = new Set();
  for (const name of all.keys()) {
    let directory = path.posix.dirname(name);
    while (!directories.has(directory)) {
      directories.add(directory);
      const parent = path.posix.dirname(directory);
      if (parent === directory) break;
      directory = parent;
    }
  }
  const roots = request.roots.map(name => canonical(path.posix.join(virtualRoot, relative(name))));
  if (new Set(roots).size !== roots.length || roots.some(name => !files.has(name))) throw Error('compiler root absent');
  const outputs = new Map(), loaded = new Set(); let outputBytes=0;
  const modes = request.operation === 'compile' ? ['cjs', 'esm'] : ['node16', 'nodenext'];
  const diagnostics = [];
  for (const mode of modes) {
    const context = new Map(all);
    if (request.operation === 'compile') context.set(virtualRoot+'/package.json', JSON.stringify({type:mode==='esm'?'module':'commonjs'}));
    const options = {
      strict: true, target: ts.ScriptTarget.ES2022,
      types: [], typeRoots: [], lib: ['lib.es2022.d.ts'],
      skipLibCheck: false, noEmitOnError: true,
      declaration: request.operation === 'compile',
      noEmit: request.operation !== 'compile',
      module: mode === 'cjs' || mode === 'node16' ? ts.ModuleKind.Node16 : ts.ModuleKind.NodeNext,
      moduleResolution: mode === 'cjs' || mode === 'node16' ? ts.ModuleResolutionKind.Node16 : ts.ModuleResolutionKind.NodeNext,
      ...(request.operation === 'compile' ? {rootDir:path.posix.join(virtualRoot, 'src'),outDir:path.posix.join(virtualRoot, mode),esModuleInterop:true} : {}),
    };
    const host = {
      getSourceFile(name, languageVersion) {
        const normalized = canonical(name), content = context.get(normalized);
        if (content === undefined) return undefined;
        loaded.add(normalized);
        const source=ts.createSourceFile(normalized, content, languageVersion);
        const provider=normalized.match(/^(.*\/_providers\/[^/]+\/artifact)\//);
        if(files.has(normalized)) {
          if(source.libReferenceDirectives.length || source.hasNoDefaultLib) throw Error('candidate cannot expand selected ES2022 compiler libraries');
          if(provider && source.typeReferenceDirectives.length) throw Error('sealed provider cannot import registry type directives');
          for(const reference of source.referencedFiles) {
            const label=provider?'sealed provider reference':'candidate reference';
            if(path.posix.isAbsolute(reference.fileName) || /[\\:]/.test(reference.fileName)) throw Error(label+' must remain relative');
            const target=path.posix.resolve(path.posix.dirname(normalized),reference.fileName);
            if(!files.has(target) || provider && !target.startsWith(provider[1]+'/')) throw Error(label+' leaves supplied inventory');
          }
        }
        return source;
      },
      getDefaultLibFileName: () => canonical(path.posix.join(compilerRoot, 'lib/lib.es2022.d.ts')),
      getDefaultLibLocation: () => canonical(path.posix.join(compilerRoot, 'lib')),
      writeFile(name, content) {
        const normalized = canonical(name), prefix = virtualRoot + '/' + mode + '/';
        if (!normalized.startsWith(prefix) || !normalized.endsWith('.js') && !normalized.endsWith('.d.ts') || outputs.has(normalized)) throw Error('compiler output leaves format namespace');
        if (outputs.size >= 4096 || (outputBytes += Buffer.byteLength(content)) > 32*1024*1024) throw Error('compiler output bound');
        outputs.set(normalized, content);
      },
      getCurrentDirectory: () => virtualRoot,
      getDirectories: () => [], readDirectory: () => [],
      getCanonicalFileName: name => canonical(name),
      useCaseSensitiveFileNames: () => true, getNewLine: () => '\n',
      fileExists: name => context.has(canonical(name)),
      readFile: name => context.get(canonical(name)),
      directoryExists: name => directories.has(canonical(name)),
      realpath: name => canonical(name),
    };
    host.resolveModuleNameLiterals = (literals, containingFile, redirectedReference, options, containingSourceFile) => literals.map(literal => {
      const resolution=ts.resolveModuleName(literal.text,containingFile,options,host,undefined,redirectedReference,ts.getModeForUsageLocation(containingSourceFile,literal,options));
      const resolved=resolution.resolvedModule?.resolvedFileName;
      if(!resolved || !files.has(canonical(resolved))) throw Error('declaration or source module has no physical resolution in supplied inventory');
      const provider=canonical(containingFile).match(/^(.*\/_providers\/[^/]+\/artifact)\//);
      if(provider && !canonical(resolved).startsWith(provider[1]+'/')) throw Error('sealed provider declaration leaves provider inventory');
      return resolution;
    });
    host.resolveTypeReferenceDirectiveReferences = (references, containingFile, redirectedReference, options, containingSourceFile) => references.map(reference => {
      const name=typeof reference==='string'?reference:reference.fileName;
      const mode=typeof reference==='string'?containingSourceFile?.impliedNodeFormat:reference.resolutionMode??containingSourceFile?.impliedNodeFormat;
      const result=ts.resolveTypeReferenceDirective(name,containingFile,options,host,redirectedReference,undefined,mode);
      if(!result.resolvedTypeReferenceDirective || !files.has(canonical(result.resolvedTypeReferenceDirective.resolvedFileName))) throw Error('type directive has no physical resolution in supplied inventory');
      return result;
    });
    const program = ts.createProgram(roots, options, host);
    const errors = ts.getPreEmitDiagnostics(program);
    if (!errors.length && request.operation === 'compile') errors.push(...program.emit().diagnostics);
    if(diagnostics.length+errors.length>128) throw Error('compiler diagnostic count bound');
    for (const error of errors) {
      const message=ts.flattenDiagnosticMessageText(error.messageText,'\n');
      if(Buffer.byteLength(message)>8192) throw Error('compiler diagnostic byte bound');
      diagnostics.push({mode,code:error.code,category:error.category,message});
    }
  }
  const result = {version:1, compiler:ts.version, success:diagnostics.length === 0, diagnostics, inputs:[...loaded].filter(name => files.has(name)).map(name => name.slice(virtualRoot.length+1)).sort(), outputs:[...(diagnostics.length ? new Map() : outputs)].sort(([a],[b]) => a < b ? -1 : a > b ? 1 : 0).map(([name,content])=>({path:name.slice(virtualRoot.length+1),content:Buffer.from(content).toString('base64')}))};
  process.stdout.write(JSON.stringify(result));
})().catch(error => {process.stderr.write(String(error.message));process.exitCode=1;});
