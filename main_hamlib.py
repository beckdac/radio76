import Hamlib

def main():
    print("Hello from radio76!")

    # Initialize a new rig object (example model 2 for NET rigctl, 
    # or specific model number for direct serial control)
    # Note: This is an illustrative example, exact API calls may vary by Hamlib version
    Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_ERR)
    rig = Hamlib.Rig(1049) 

    try:
        # Configure the rig's communication parameters (e.g., serial port, baud rate)
        # For a direct connection, you'd specify a device path like "/dev/ttyUSB0" or "COM1"
        # rig.set_conf("rig_pathname", "/dev/ttyUSB0") 
        # rig.set_conf("serial_speed", "4800") 

        # For net rigctl connection (if using rigctld):
        rig.set_conf("rig_pathname", "COM7")
        rig.set_conf("serial_speed", "38400") 
    
        # Open the rig connection
        rig.open()

        # Get the frequency
        freq = rig.get_freq()
        print(f"Frequency: {freq}")

        # Set the frequency
        # rig.set_freq(145000000) # Example: set to 145 MHz

        # Get the mode and passband
        mode, passband = rig.get_mode()
        print(f"Mode: {mode}, Passband: {passband}")

    except Hamlib.HamlibError as e:
        print(f"Hamlib Error: {e}")
    finally:
        # Close the rig connection
        if rig:
            rig.close()


if __name__ == "__main__":
    main()
