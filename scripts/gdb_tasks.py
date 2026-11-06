"""A gdb script: every FreeRTOS task of a PRG32 QEMU firmware, with its backtrace.

    riscv32-esp-elf-gdb -batch -ex "target remote :PORT" -x scripts/gdb_tasks.py PRG32.elf

QEMU's gdb stub knows only the CPU, not the tasks. Each task that is not running
has its registers saved on its own stack, in the order of ESP-IDF's RvExcFrame
(mepc, then x1..x31). For each task the script loads those into the CPU, prints a
backtrace, and puts the real registers back before it detaches. Used by
scripts/qemu_netplay.py when a console stops answering."""

import gdb  # noqa: F401  (provided by gdb)

REGS = ["pc", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1",
        "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7",
        "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11",
        "t3", "t4", "t5", "t6"]


def u32(expr):
    return int(gdb.parse_and_eval(expr)) & 0xFFFFFFFF


def list_owners(lst):
    """The pvOwner of every item of a FreeRTOS List_t (an lvalue expression)."""
    out = []
    n = u32(f"({lst}).uxNumberOfItems")
    end = int(gdb.parse_and_eval(f"&({lst}).xListEnd"))
    item = u32(f"({lst}).xListEnd.pxNext")
    for _ in range(n + 1):
        if item == end or not item:
            break
        out.append(u32(f"((ListItem_t *){item})->pvOwner"))
        item = u32(f"((ListItem_t *){item})->pxNext")
    return out


def all_tasks():
    tasks = {}
    prios = int(gdb.parse_and_eval("sizeof(pxReadyTasksLists) / sizeof(pxReadyTasksLists[0])"))
    for p in range(prios):
        for t in list_owners(f"pxReadyTasksLists[{p}]"):
            tasks[t] = "ready"
    for name in ("xDelayedTaskList1", "xDelayedTaskList2", "xPendingReadyList",
                 "xSuspendedTaskList", "xTasksWaitingTermination"):
        try:
            for t in list_owners(name):
                tasks.setdefault(t, name)
        except gdb.error:
            pass
    return tasks


def main():
    running = u32("pxCurrentTCBs[0]")
    saved = {r: u32(f"${r}") for r in REGS}
    tasks = all_tasks()
    tasks.setdefault(running, "running")
    try:
        for tcb, state in tasks.items():
            name = gdb.parse_and_eval(f"((struct tskTaskControlBlock *){tcb})->pcTaskName").string()
            prio = u32(f"((struct tskTaskControlBlock *){tcb})->uxPriority")
            print(f"=== task {name!r} prio {prio} {state}{' (current)' if tcb == running else ''}")
            if tcb != running:
                top = u32(f"((struct tskTaskControlBlock *){tcb})->pxTopOfStack")
                for i, r in enumerate(REGS):
                    gdb.execute(f"set ${r} = *(unsigned int *){top + 4 * i}", to_string=True)
            try:
                print(gdb.execute("bt 14", to_string=True), end="")
            except gdb.error as e:
                print(f"  (no backtrace: {e})")
            for r in REGS:
                gdb.execute(f"set ${r} = {saved[r]}", to_string=True)
    finally:
        for r in REGS:
            gdb.execute(f"set ${r} = {saved[r]}", to_string=True)


main()
