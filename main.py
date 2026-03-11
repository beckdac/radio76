import pyfldigi

def main():
    print("Hello from radio76!")

    global fldigi

    fldigi = pyfldigi.Client()

    print(f"frequency: {fldigi.rig.frequency}")
    print(f"     mode: {fldigi.rig.mode}")

    print(f"found {len(fldigi.rig.modes)} modes available")
    print(f"{fldigi.rig.modes}")


if __name__ == "__main__":
    main()
