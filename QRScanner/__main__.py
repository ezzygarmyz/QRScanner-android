
import asyncio

from java import dynamic_proxy, cast
from java.util import Arrays
from java.lang import Runnable
from android.content import Context, ClipData, ClipboardManager
from android.widget import Toast
from android.content.res import Configuration
from androidx.activity.result import ActivityResultCallback
from com.journeyapps.barcodescanner import ScanOptions, ScanContract
from org.beeware.android import MainActivity, IPythonApp, PortraitCaptureActivity

from toga import App, MainWindow, Box, Label, Button, Switch
from toga.style.pack import Pack
from toga.constants import COLUMN, CENTER, BOLD
from toga.colors import rgb, WHITE, GREEN, BLACK, YELLOW


class RunnableProxy(dynamic_proxy(Runnable)):
    def __init__(self, func):
        super().__init__()
        self.func = func
        
    def run(self):
        self.func()


class QRCallbackProxy(dynamic_proxy(ActivityResultCallback)):
    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner

    def onActivityResult(self, result):
        if result and result.getContents():
            contents = result.getContents()
            self.scanner._set_result(contents)
        else:
            self.scanner._set_result(None)
    


class QRScanner:
    def __init__(self):
        self.activity = MainActivity.singletonThis
        self._launcher = None
        self._future = None

        scan_contract = ScanContract()
        callback_proxy = QRCallbackProxy(self)
        self._launcher = self.activity.registerForActivityResult(scan_contract, callback_proxy)

    async def start_scan(self, beep=False, torch=False):
        if self._launcher is None:
            raise RuntimeError("QRScanner callback must be set before scanning")

        self._future = asyncio.get_event_loop().create_future()

        options = ScanOptions()
        options.setPrompt("Scan a QR Code")
        options.setBeepEnabled(beep)
        options.setCaptureActivity(PortraitCaptureActivity)
        options.setDesiredBarcodeFormats(Arrays.asList("QR_CODE"))
        options.setTorchEnabled(torch)

        self.activity.runOnUiThread(RunnableProxy(lambda: self._launcher.launch(options)))
        return await self._future

    def _set_result(self, contents):
        if self._future and not self._future.done():
            self._future.set_result(contents)



class PythonAppProxy(dynamic_proxy(IPythonApp)):
    def __init__(self):
        super().__init__()

        self._back_callback = None

    def onBackPressed(self):
        if self._back_callback:
            try:
                result = self._back_callback()
                if isinstance(result, bool):
                    return result
            except Exception as e:
                print("Back callback error:", e)
        return False



class QRScannerGUI(MainWindow):
    def __init__(self):
        super().__init__()

        version = self.app.version
        self._qr_scanner = QRScanner()

        ui_mode = self.get_ui_mode()
        if ui_mode == "dark":
            color = WHITE
            background_color = rgb(40,43,48)
            button_color = GREEN
        else:
            color = BLACK
            background_color = WHITE
            button_color = YELLOW

        self.main_box = Box(
            style=Pack(
                direction = COLUMN,
                background_color=background_color,
                flex = 1,
                alignment = CENTER
            )
        )

        self.app_version = Label(
            text=f"v {version}",
            style=Pack(
                color = color,
                background_color =background_color,
                flex = 1,
                text_align = CENTER,
                font_size=15,
                font_weight=BOLD,
                padding = (20,0,30,0)
            )
        )

        self.widgets_box = Box(
            style=Pack(
                direction = COLUMN,
                background_color = background_color,
                flex = 1
            )
        )

        self.torch_switch = Switch(
            text="Torch :",
            value=False,
            style=Pack(
                color = color,
                background_color = background_color,
                font_size = 14,
                padding= (15,20,0,20)
            )
        )

        self.beep_switch = Switch(
            text="Beep :",
            value=False,
            style=Pack(
                color = color,
                background_color = background_color,
                font_size = 14,
                padding= (10,20,0,20)
            )
        )

        self.scan_button = Button(
            text="Scan QR",
            style=Pack(
                color = color,
                background_color = button_color,
                font_size = 14,
                alignment = CENTER,
                padding= (10,10,5,10)
            ),
            on_press=self.scan_qr
        )

        self.content = self.main_box
        self.main_box.add(
            self.widgets_box,
            self.app_version
        )
        self.widgets_box.add(
            self.beep_switch,
            self.torch_switch,
            self.scan_button
        )


    
    def scan_qr(self, button):
        beep = self.beep_switch.value
        torch = self.torch_switch.value
        asyncio.ensure_future(self.handle_scan(beep, torch))


    async def handle_scan(self, beep, torch):
        result = await self._qr_scanner.start_scan(beep, torch)
        if result:

            def on_result(widget, result):
                if result is None:
                    context = MainActivity.singletonThis.getApplicationContext()
                    clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE)
                    clipboard_manager = cast(ClipboardManager, clipboard)
                    clip = ClipData.newPlainText("QR Code", result)
                    clipboard_manager.setPrimaryClip(clip)
                    Toast.makeText(context, "Copied to clipboard", Toast.LENGTH_SHORT).show()

            self.info_dialog(
                title="QR Code Scanned",
                message=f"Result:\n{result}",
                on_result=on_result
            )

    def get_ui_mode(self):
        try:
            config = MainActivity.singletonThis.getResources().getConfiguration()
            ui_mode = config.uiMode
            is_dark = (ui_mode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
            return "dark" if is_dark else "light"
        except Exception as e:
            print("Theme detection failed:", e)
            return "unknown"



class QRScanner(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.proxy = PythonAppProxy()
        self.proxy._back_callback = self.on_back_pressed


    def startup(self):
        MainActivity.setPythonApp(self.proxy)
        self.main_window = QRScannerGUI()
        self.main_window.show()


    def on_back_pressed(self):
        def on_result(widget, result):
            if result is True:
                MainActivity.singletonThis.finish()

        self.main_window.question_dialog(
            title="Exit app",
            message="Are you sure you want exit the app",
            on_result=on_result
        )
        return True
        

def main():
    app = QRScanner(
        formal_name = "QRScanner",
        app_id = "com.qrscanner",
        home_page = "https://example.com",
        author = "BTCZCommunity",
        version = "1.1.0"
    )
    app.main_loop()

if __name__ == "__main__":
    main()
