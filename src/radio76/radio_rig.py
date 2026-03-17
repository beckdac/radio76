import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Label, Button, Select, RadioSet, RadioButton
from textual.containers import Vertical, Horizontal, Grid

MODES = [ ("AM", "AM"), ("CW", "CW"), ("USB", "USB"), ("LSB", "LSB"), ("RTTY", "RTTY"), ("FM", "FM"), ("CWR", "CWR"), ("RTTYR", "RTTYR"), ("PKTLSB", "PKTLSB"), ("PKTUSB", "PKTUSB"), ("FM-D", "FM-D"), ("FMN", "FMN"), ("AMN", "AMN"), ("PKTFMN", "PKTFMN") ]

class RigControlApp(App):
    CSS = """
    Grid { grid-size: 2; grid-gutter: 1; padding: 1; }
    .box { border: solid green; padding: 1; }
    #freq-display { color: cyan; text-align: center; }
    Button { width: 100%; margin-top: 1; }
    Label { margin-top: 1; }
    """

    def __init__(self, host="192.168.1.142", port=4532):
        super().__init__()
        self.host, self.port = host, port
        self.reader = self.writer = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid():
            # Frequency & VFO Column
            with Vertical(classes="box"):
                yield Label("Frequency (Hz)")
                yield Label("00000000", id="freq-display")
                yield Input(placeholder="Set Hz...", id="freq-input")
                
                yield Label("Active VFO")
                with RadioSet(id="vfo-select"):
                    yield RadioButton("VFOA", id="VFOA", value=True)
                    yield RadioButton("VFOB", id="VFOB")
            
            # Mode & Control Column
            with Vertical(classes="box"):
                yield Label("Operating Mode")
                yield Select(MODES, id="mode-select", prompt="Select Mode")
                
                yield Label("Quick Actions")
                yield Button("Sync from Rig", variant="primary", id="sync")
                yield Button("Quit", variant="error", id="quit")
        yield Footer()

    async def on_mount(self) -> None:
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            await self.sync_all()
        except Exception as e:
            self.notify(f"Connection Failed: {e}", severity="error")

    async def send(self, cmd: str) -> str:
        if not self.writer: return ""
        self.writer.write(f"{cmd}\n".encode())
        await self.writer.drain()
        return (await self.reader.readline()).decode().strip()

    async def sync_all(self):
        """Pull current state from the rig."""
        # Get Freq
        self.query_one("#freq-display").update(await self.send("f"))
        # Get Mode (returns two lines: mode\nwidth)
        mode = await self.send("m")
        print(f"mode {mode}")
        self.query_one("#mode-select").value = mode
        # Get VFO
        vfo = await self.send("v")
        if vfo in ["VFOA", "VFOB"]:
            self.query_one(f"#{vfo}").value = True

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "freq-input" and event.value.isdigit():
            await self.send(f"F {event.value}")
            await self.sync_all()
            event.input.value = ""

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.value:
            # 'M' takes mode and passband (0 = default width)
            await self.send(f"M {event.value} 0")

    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        vfo_name = str(event.pressed.label)
        await self.send(f"V {vfo_name}")
        await self.sync_all() # Update freq/mode for the new VFO

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sync":
            await self.sync_all()
        elif event.button.id == "quit":
            self.exit()

if __name__ == "__main__":
    RigControlApp().run()
