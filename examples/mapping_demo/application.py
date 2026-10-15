from demo_device.device import is_ready

if is_ready(_force=True):
    print("ready")
else:
    print("not ready")
