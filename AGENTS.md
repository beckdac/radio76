This is a Python code base for controling an HF radio using Python's Hamlib bindings found here: https://github.com/Hamlib/Hamlib/blob/master/bindings/README.python

The user interface is provided by the textual package.

The user interface should have multiple textual tabs. They are:
* VFO A
* VFO B
* Modem
The tabs VFO A and VFO B have displays and controls for the VFO A and VFO B including frequency and mode.  The frequency should be displayed in a large font.

For the Hamlib setup.  The default device should be COM7 and the default radio type 1049. After the user interface is initialized, the current VFO A and B frequencies and modes should be read and displayed using textual.
