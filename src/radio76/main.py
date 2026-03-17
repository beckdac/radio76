from textual.app import App, ComposeResult
from textual.widgets import Tabs, TabPane, Label, Input
from textual.events import Mount
import hamlib

CSS = """
Label {
    font-size: 24;
}
"""

class RadioApp(App):
    def compose(self) -> ComposeResult:
        yield Tabs(
            TabPane("VFO A", Label("Frequency: ", id="vfoa_freq"), Input(placeholder="Enter frequency", id="vfoa_input")),
            TabPane("VFO B", Label("Frequency: ", id="vfob_freq"), Input(placeholder="Enter frequency", id="vfob_input")),
            TabPane("Modem", Label("Modem settings go here"))
        )

    def on_mount(self) -> None:
        # Initialize Hamlib with COM7 and radio type 1049
        Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_ERR)
        self.rig = Hamlib.Rig(1049)
        self.rig.set_conf("rig_pathname", "COM7")
        self.rig.set_conf("serial_speed", "38400")

        # Open the rig connection
        self.rig.open()

        
        # Read and display current frequencies
        vfoa_freq = self.rig.get_freq(hamlib.RIG_VFO_A)
        vfob_freq = self.rig.get_freq(hamlib.RIG_VFO_B)
        
        self.query_one("#vfoa_freq").update(f"Frequency: {vfoa_freq} Hz")
        self.query_one("#vfob_freq").update(f"Frequency: {vfob_freq} Hz")

RadioApp().run()
