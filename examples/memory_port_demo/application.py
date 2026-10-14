from demo_memory_ports.memory import ManualMemoryRegion

memory: ManualMemoryRegion = ManualMemoryRegion.integer(minimum=0, maximum=255)
memory.assign(42)
if memory.value == 42:
    print("ok")
memory.release()
