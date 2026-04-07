import ctypes

dlls = ["Fwlib64.dll", "fwlib0DN64.dll", "fwlib30i64.dll", "fwlib0iD.dll"]
base_path = r"D:\Hardik's stuff\Neelkanth Int\MISC\fanuc FOCAS\m3"

print("=== cnc_rdactdt ===")
for dll_name in dlls:
    dll_path = base_path + "\\" + dll_name
    try:
        dll = ctypes.WinDLL(dll_path)
        if hasattr(dll, "cnc_rdactdt"):
            print(f"{dll_name}: EXISTS")
        else:
            print(f"{dll_name}: NOT FOUND")
    except Exception as e:
        print(f"{dll_name}: Error - {e}")

print()
print("=== cnc_rdprogline2 ===")
for dll_name in dlls:
    dll_path = base_path + "\\" + dll_name
    try:
        dll = ctypes.WinDLL(dll_path)
        if hasattr(dll, "cnc_rdprogline2"):
            print(f"{dll_name}: EXISTS")
        else:
            print(f"{dll_name}: NOT FOUND")
    except Exception as e:
        print(f"{dll_name}: Error - {e}")