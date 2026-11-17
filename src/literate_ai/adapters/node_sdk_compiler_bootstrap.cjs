"use strict";
const crypto=require("node:crypto"),vm=require("node:vm");
const [helperSHA,sdkSHA]=process.argv.slice(1);
const own=(value,keys)=>value&&typeof value==="object"&&!Array.isArray(value)&&Object.keys(value).sort().join("|")===keys.sort().join("|");
const sha=bytes=>crypto.createHash("sha256").update(bytes).digest("hex");
(async()=>{
  if(!/^[a-f0-9]{64}$/.test(helperSHA)||!/^[a-f0-9]{64}$/.test(sdkSHA)||process.argv.length!==3)throw Error("compiler command identity invalid");
  let size=0;const chunks=[];
  for await(const chunk of process.stdin){if((size+=chunk.length)>64*1024*1024)throw Error("compiler packet byte bound");chunks.push(chunk);}
  const packet=JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if(!own(packet,["helper","compiler_snapshot","request"])||typeof packet.helper!=="string"||Buffer.byteLength(packet.helper)>16384||sha(Buffer.from(packet.helper))!==helperSHA)throw Error("compiler helper differs from selected bytes");
  if(typeof packet.compiler_snapshot!=="string"||Buffer.byteLength(packet.compiler_snapshot)>48*1024*1024||sha(Buffer.from(packet.compiler_snapshot))!==sdkSHA)throw Error("compiler SDK differs from selected bytes");
  if(!own(packet.request,["version","operation","files","roots"]))throw Error("compiler request shape");
  const module={exports:{}};
  const load=vm.runInThisContext("(function(require,module,exports){"+packet.helper+"\n})",{filename:"/__literate_framework__/node_sdk_compiler.cjs"});
  load(require,module,module.exports);
  if(typeof module.exports!=="function")throw Error("compiler helper entrypoint absent");
  const result=module.exports({...packet.request,compiler_files:JSON.parse(packet.compiler_snapshot)});
  process.stdout.write(JSON.stringify(result));
})().catch(error=>{process.stderr.write(String(error.message).slice(0,8192));process.exitCode=1;});
