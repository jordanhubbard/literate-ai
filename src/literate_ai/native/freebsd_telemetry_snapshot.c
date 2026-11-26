/*
 * Read-only, bounded FreeBSD reaper resource snapshot.
 *
 * This program is a mechanical reader, not an execution/admission owner. Its
 * caller must bind its selected PID and generation to the ORIGINAL live native
 * runner and private guardian channel before using any numbers. No decoded
 * output can create that owner. Provisioning/compilation is outside queries.
 *
 * Native headers determine kinfo_proc/procctl layouts; no Python offset guesses.
 * Only STATUS/GETPIDS and selected-PID sysctl reads are used. There is no signal,
 * reaper acquisition, process-group scan, command/environment/path output, file
 * write, installation or clock mutation.
 *
 * CPU is own+already-reaped-child runtime over every currently live member,
 * including the guardian. These disjoint accounting frontiers include short-
 * lived work reaped by its actual parent. A changed frontier refuses the whole
 * sample. RSS is the SUM of CURRENT per-process resident pages, not peak RSS or
 * unique physical pages; shared pages may appear in more than one process.
 * Disk/network byte accounting is NOT implemented or claimed by this reader.
 */

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __FreeBSD__
#include <sys/types.h>
#include <sys/param.h>
#include <sys/proc.h>
#include <sys/procctl.h>
#include <sys/sysctl.h>
#include <sys/user.h>

#define MAX_MEMBERS 128
#define MAX_CAPTURE_NS UINT64_C(2000000000)
#define MAX_SIGNED_VALUE UINT64_C(9223372036854775807)

struct member {
    struct kinfo_proc process;
    pid_t reaper;
    unsigned flags;
    uint64_t cpu_self_ns;
    uint64_t cpu_children_ns;
    uint64_t rss_bytes;
};

struct snapshot {
    struct member members[MAX_MEMBERS];
    size_t count;
    uint64_t cpu_ns;
    uint64_t rss_bytes;
};

static struct snapshot before, after;
static uint64_t until_ns;
static long page_bytes;

static uint64_t
monotonic_ns(void)
{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0 || value.tv_sec < 0 ||
        value.tv_nsec < 0 || value.tv_nsec >= 1000000000 ||
        (uint64_t)value.tv_sec >
        (MAX_SIGNED_VALUE - (uint64_t)value.tv_nsec) / UINT64_C(1000000000))
        return 0;
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) +
        (uint64_t)value.tv_nsec;
}

static int
boundary(void)
{
    uint64_t now = monotonic_ns();
    if (now == 0 || now >= until_ns) {
        errno = ETIMEDOUT;
        return -1;
    }
    return 0;
}

static int
timeval_ns(struct timeval value, uint64_t *result)
{
    if (value.tv_sec < 0 || value.tv_usec < 0 || value.tv_usec >= 1000000 ||
        (uint64_t)value.tv_sec > MAX_SIGNED_VALUE / UINT64_C(1000000000)) {
        errno = EOVERFLOW;
        return -1;
    }
    *result = (uint64_t)value.tv_sec * UINT64_C(1000000000) +
        (uint64_t)value.tv_usec * UINT64_C(1000);
    if (*result > MAX_SIGNED_VALUE) {
        errno = EOVERFLOW;
        return -1;
    }
    return 0;
}

static int
process_info(pid_t pid, struct kinfo_proc *result)
{
    int mib[] = { CTL_KERN, KERN_PROC, KERN_PROC_PID, pid };
    size_t size = sizeof(*result);
    if (boundary() != 0)
        return -1;
    memset(result, 0, sizeof(*result));
    if (sysctl(mib, 4, result, &size, NULL, 0) != 0)
        return -1;
    if (size != sizeof(*result) || result->ki_structsize != (int)sizeof(*result) ||
        result->ki_pid != pid || result->ki_start.tv_sec <= 0 ||
        result->ki_start.tv_usec < 0 || result->ki_start.tv_usec >= 1000000) {
        errno = ESRCH;
        return -1;
    }
    /* exit1 folds already-reaped-child CPU into the exiting process runtime.
     * Reject BOTH opening and closing kinfo reads in that phase, otherwise
     * adding ki_childtime can double count even with a stable PID frontier.
     * Earlier GETPIDS flags alone cannot close this exit-state race. */
    if (result->ki_stat == SZOMB || (result->ki_flag & P_WEXIT) != 0) {
        errno = EAGAIN;
        return -1;
    }
    if (result->ki_uid != geteuid()) {
        errno = EACCES;
        return -1;
    }
    return 0;
}

static int
same_generation(const struct kinfo_proc *a, const struct kinfo_proc *b)
{
    return a->ki_pid == b->ki_pid && a->ki_ppid == b->ki_ppid &&
        a->ki_start.tv_sec == b->ki_start.tv_sec &&
        a->ki_start.tv_usec == b->ki_start.tv_usec && a->ki_uid == b->ki_uid;
}

static int
reaper_status(pid_t pid, struct procctl_reaper_status *result)
{
    if (boundary() != 0)
        return -1;
    memset(result, 0, sizeof(*result));
    return procctl(P_PID, pid, PROC_REAP_STATUS, result);
}

static int
find_member(const struct snapshot *value, pid_t pid)
{
    size_t i;
    for (i = 0; i < value->count; ++i)
        if (value->members[i].process.ki_pid == pid)
            return (int)i;
    return -1;
}

static int
append_member(struct snapshot *value, pid_t pid, pid_t reaper, unsigned flags)
{
    struct member *member;
    struct kinfo_proc closing;
    struct procctl_reaper_status status;
    if (value->count >= MAX_MEMBERS) {
        errno = EOVERFLOW;
        return -1;
    }
    if (find_member(value, pid) >= 0) {
        errno = EAGAIN;
        return -1;
    }
    member = &value->members[value->count];
    if (process_info(pid, &member->process) != 0 ||
        reaper_status(pid, &status) != 0 || process_info(pid, &closing) != 0)
        return -1;
    if (!same_generation(&member->process, &closing) ||
        ((flags & REAPER_PIDINFO_REAPER) != 0) !=
        ((status.rs_flags & REAPER_STATUS_OWNED) != 0) ||
        (!(status.rs_flags & REAPER_STATUS_OWNED) && status.rs_reaper != reaper)) {
        errno = EAGAIN;
        return -1;
    }
    member->process = closing;
    member->reaper = reaper;
    member->flags = flags;
    ++value->count;
    return 0;
}

static int
read_owned_reaper(struct snapshot *value, size_t index)
{
    struct procctl_reaper_pidinfo pids[MAX_MEMBERS + 1];
    struct procctl_reaper_pids request;
    struct procctl_reaper_status opening, closing;
    struct kinfo_proc generation;
    struct member *member = &value->members[index];
    pid_t pid = member->process.ki_pid;
    size_t i, count = 0;

    if (process_info(pid, &generation) != 0 ||
        !same_generation(&member->process, &generation)) {
        errno = EAGAIN;
        return -1;
    }
    if (reaper_status(pid, &opening) != 0)
        return -1;
    if (!(opening.rs_flags & REAPER_STATUS_OWNED)) {
        errno = EAGAIN;
        return -1;
    }
    if (opening.rs_descendants > MAX_MEMBERS - value->count) {
        errno = EOVERFLOW;
        return -1;
    }
    memset(pids, 0, sizeof(pids));
    memset(&request, 0, sizeof(request));
    request.rp_count = MAX_MEMBERS + 1;
    request.rp_pids = pids;
    if (boundary() != 0 ||
        procctl(P_PID, pid, PROC_REAP_GETPIDS, &request) != 0)
        return -1;
    for (i = 0; i < MAX_MEMBERS + 1; ++i) {
        if (!(pids[i].pi_flags & REAPER_PIDINFO_VALID))
            break;
        ++count;
        if (pids[i].pi_pid <= 0 || pids[i].pi_pid == pid ||
            (pids[i].pi_flags & ~(REAPER_PIDINFO_VALID |
            REAPER_PIDINFO_CHILD | REAPER_PIDINFO_REAPER)) != 0) {
            errno = EAGAIN;
            return -1;
        }
        if (append_member(value, pids[i].pi_pid, pid, pids[i].pi_flags) != 0)
            return -1;
    }
    if (count != opening.rs_descendants || reaper_status(pid, &closing) != 0 ||
        opening.rs_descendants != closing.rs_descendants ||
        opening.rs_children != closing.rs_children ||
        !(closing.rs_flags & REAPER_STATUS_OWNED) ||
        process_info(pid, &generation) != 0 ||
        !same_generation(&member->process, &generation)) {
        errno = EAGAIN;
        return -1;
    }
    return 0;
}

static int
validate_lineage(const struct snapshot *value)
{
    size_t i, depth;
    for (i = 1; i < value->count; ++i) {
        int cursor = (int)i;
        for (depth = 0; depth < value->count; ++depth) {
            cursor = find_member(value, value->members[cursor].process.ki_ppid);
            if (cursor == 0)
                break;
            if (cursor < 0) {
                errno = EAGAIN;
                return -1;
            }
        }
        if (depth == value->count) {
            errno = EAGAIN;
            return -1;
        }
    }
    return 0;
}

static int
capture(pid_t root, struct snapshot *value)
{
    size_t i;
    uint64_t own, children, rss;
    memset(value, 0, sizeof(*value));
    if (append_member(value, root, root,
        REAPER_PIDINFO_VALID | REAPER_PIDINFO_REAPER) != 0)
        return -1;
    /* The observer must be a sibling launched by the actual original parent,
     * not a general arbitrary-PID query. Caller still proves its exact nonce. */
    if (value->members[0].process.ki_ppid != getppid()) {
        errno = EACCES;
        return -1;
    }
    for (i = 0; i < value->count; ++i)
        if ((value->members[i].flags & REAPER_PIDINFO_REAPER) &&
            read_owned_reaper(value, i) != 0)
            return -1;
    if (validate_lineage(value) != 0)
        return -1;
    for (i = 0; i < value->count; ++i) {
        struct member *member = &value->members[i];
        if (member->process.ki_runtime > MAX_SIGNED_VALUE / 1000 ||
            timeval_ns(member->process.ki_childtime, &children) != 0 ||
            member->process.ki_rssize < 0 ||
            (uint64_t)member->process.ki_rssize >
            MAX_SIGNED_VALUE / (uint64_t)page_bytes) {
            errno = EOVERFLOW;
            return -1;
        }
        own = member->process.ki_runtime * 1000;
        rss = (uint64_t)member->process.ki_rssize * (uint64_t)page_bytes;
        if (own > MAX_SIGNED_VALUE - children ||
            own + children > MAX_SIGNED_VALUE - value->cpu_ns ||
            rss > MAX_SIGNED_VALUE - value->rss_bytes) {
            errno = EOVERFLOW;
            return -1;
        }
        member->cpu_self_ns = own;
        member->cpu_children_ns = children;
        member->rss_bytes = rss;
        value->cpu_ns += own + children;
        value->rss_bytes += rss;
    }
    return boundary();
}

static int
compatible_frontier(const struct snapshot *a, const struct snapshot *b)
{
    size_t i;
    if (a->count != b->count)
        return 0;
    for (i = 0; i < a->count; ++i) {
        const struct member *old = &a->members[i];
        int index = find_member(b, old->process.ki_pid);
        const struct member *current;
        if (index < 0)
            return 0;
        current = &b->members[index];
        if (!same_generation(&old->process, &current->process) ||
            old->reaper != current->reaper || old->flags != current->flags ||
            old->cpu_children_ns != current->cpu_children_ns ||
            old->cpu_self_ns > current->cpu_self_ns)
            return 0;
    }
    return a->cpu_ns <= b->cpu_ns;
}

static int
refusal(int error)
{
    const char *status = "unavailable";
    if (error == EACCES || error == EPERM)
        status = "denied";
    else if (error == EOVERFLOW)
        status = "limit";
    else if (error == ESRCH || error == EAGAIN || error == ENOENT)
        status = "unstable";
    else if (error == ETIMEDOUT)
        status = "expired";
    printf("{\"schema\":\"literate-ai/native-freebsd-resource-snapshot@1\","
        "\"status\":\"%s\"}\n", status);
    return 2;
}

int
main(int argc, char **argv)
{
    char *end;
    long parsed;
    uint64_t started, finished;
    struct timespec wall;
    size_t i;

    if (argc != 2 || argv[1][0] < '1' || argv[1][0] > '9')
        return refusal(EINVAL);
    errno = 0;
    parsed = strtol(argv[1], &end, 10);
    if (errno || *end || parsed <= 1 || parsed > INT_MAX)
        return refusal(EINVAL);
    started = monotonic_ns();
    page_bytes = sysconf(_SC_PAGESIZE);
    if (started == 0 || page_bytes <= 0 || page_bytes > 1048576 ||
        started > MAX_SIGNED_VALUE - MAX_CAPTURE_NS)
        return refusal(EOVERFLOW);
    until_ns = started + MAX_CAPTURE_NS;
    if (capture((pid_t)parsed, &before) != 0 ||
        capture((pid_t)parsed, &after) != 0)
        return refusal(errno);
    if (!compatible_frontier(&before, &after))
        return refusal(EAGAIN);
    finished = monotonic_ns();
    if (finished == 0 || finished >= until_ns ||
        clock_gettime(CLOCK_REALTIME, &wall) != 0 || wall.tv_sec < 0 ||
        wall.tv_nsec < 0 || wall.tv_nsec >= 1000000000 ||
        (uint64_t)wall.tv_sec >
        (MAX_SIGNED_VALUE - (uint64_t)wall.tv_nsec / 1000000) / 1000)
        return refusal(ETIMEDOUT);
    printf("{\"schema\":\"literate-ai/native-freebsd-resource-snapshot@1\","
        "\"status\":\"ok\",\"capture_started_monotonic_ns\":%" PRIu64 ","
        "\"monotonic_ns\":%" PRIu64 ",\"observed_at_ms\":%" PRIu64 ","
        "\"cpu_time_ns\":%" PRIu64 ",\"memory_resident_bytes\":%" PRIu64 ","
        "\"members\":[", started, finished,
        (uint64_t)wall.tv_sec * 1000 + (uint64_t)wall.tv_nsec / 1000000,
        after.cpu_ns, after.rss_bytes);
    for (i = 0; i < after.count; ++i) {
        const struct member *member = &after.members[i];
        printf("%s{\"pid\":%ld,\"parent_pid\":%ld,\"reaper_pid\":%ld,"
            "\"flags\":%u,\"start_seconds\":%" PRIdMAX ","
            "\"start_microseconds\":%ld,\"cpu_self_ns\":%" PRIu64 ","
            "\"cpu_children_ns\":%" PRIu64 ",\"resident_bytes\":%" PRIu64 "}",
            i ? "," : "", (long)member->process.ki_pid,
            (long)member->process.ki_ppid, (long)member->reaper, member->flags,
            (intmax_t)member->process.ki_start.tv_sec,
            (long)member->process.ki_start.tv_usec, member->cpu_self_ns,
            member->cpu_children_ns, member->rss_bytes);
    }
    printf("]}\n");
    return 0;
}
#else
int
main(void)
{
    puts("{\"schema\":\"literate-ai/native-freebsd-resource-snapshot@1\","
        "\"status\":\"unsupported\"}");
    return 2;
}
#endif
