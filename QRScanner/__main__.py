
import asyncio
import time
import os

from java import dynamic_proxy, cast, jclass
from java.util import Arrays
from java.lang import Runnable
from java.io import FileInputStream, File
from android.net import Uri
from android.content import Intent, Context, ClipData, ClipboardManager
from android.widget import Toast
from android.content.res import Configuration
from androidx.core.content import FileProvider
from androidx.documentfile.provider import DocumentFile
from androidx.activity.result import ActivityResultCallback
from com.journeyapps.barcodescanner import ScanOptions, ScanContract
from org.beeware.android import MainActivity, IPythonApp, PortraitCaptureActivity

from toga import App, MainWindow, Box, Label, Button, Switch, ImageView
from toga.style.pack import Pack
from toga.constants import COLUMN, CENTER, BOLD, ROW
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
        self._expected_timeout_time = None

        scan_contract = ScanContract()
        callback_proxy = QRCallbackProxy(self)
        self._launcher = self.activity.registerForActivityResult(scan_contract, callback_proxy)

    async def start_scan(self, beep=False, torch=False, timeout:int=None):
        if self._launcher is None:
            raise RuntimeError("QRScanner callback must be set before scanning")

        self._future = asyncio.get_event_loop().create_future()

        options = ScanOptions()
        options.setPrompt("Scan a QR Code")
        options.setBeepEnabled(beep)
        options.setCaptureActivity(PortraitCaptureActivity)
        options.setDesiredBarcodeFormats(Arrays.asList("QR_CODE"))
        options.setTorchEnabled(torch)
        if timeout:
            options.setTimeout(timeout * 1000)
            self._expected_timeout_time = time.time() + timeout
        else:
            self._expected_timeout_time = None

        self.activity.runOnUiThread(RunnableProxy(lambda: self._launcher.launch(options)))
        return await self._future

    def _set_result(self, contents):
        if contents is None and self._expected_timeout_time:
            if abs(time.time() - self._expected_timeout_time) < 2:
                contents = "__TIMEOUT__"

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
    

class FolderPickerCallback(dynamic_proxy(ActivityResultCallback)):
    def __init__(self, picker):
        super().__init__()
        self.picker = picker

    def onActivityResult(self, uri):
        if uri:
            self.picker._set_result(uri.toString())
        else:
            self.picker._set_result(None)



class FileShare:
    def __init__(self):
        self.context = MainActivity.singletonThis.getApplicationContext()
        self.package_name = self.context.getPackageName()
        self.fileprovider_authority = f"{self.package_name}.fileprovider"

    def share(self, file_path: str, mime_type="image/*", chooser_title:str=None):
        if not file_path or not os.path.exists(file_path):
            Toast.makeText(self.context, "File does not exist to share", Toast.LENGTH_SHORT).show()
            return False

        try:
            file = File(file_path)
            uri = FileProvider.getUriForFile(self.context, self.fileprovider_authority, file)

            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.setType(mime_type)
            intent.putExtra(Intent.EXTRA_STREAM, uri)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

            chooser = Intent.createChooser(intent, chooser_title)
            chooser.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self.context.startActivity(chooser)
            return True

        except Exception as e:
            Toast.makeText(self.context, f"Error sharing file: {e}", Toast.LENGTH_LONG).show()
            print("Error sharing file:", e)
            return False


class FolderPicker:
    def __init__(self):
        self.activity = MainActivity.singletonThis
        self._future = None

        callback_proxy = FolderPickerCallback(self)
        self._launcher = self.activity.registerForActivityResult(
            jclass("androidx.activity.result.contract.ActivityResultContracts$OpenDocumentTree")(),
            callback_proxy
        )

    async def pick_folder(self):
        self._future = asyncio.get_event_loop().create_future()

        def launch_intent():
            self._launcher.launch(None)

        self.activity.runOnUiThread(RunnableProxy(launch_intent))
        return await self._future

    def _set_result(self, folder_uri):
        if self._future and not self._future.done():
            self._future.set_result(folder_uri)



class QRScannerGUI(MainWindow):
    def __init__(self):
        super().__init__()

        version = self.app.version
        self._qr_scanner = QRScanner()
        self.folder_picker = FolderPicker()
        self.share_file = FileShare()

        self._qr_image = None

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

        self.qr_view = ImageView(
            style=Pack(
                background_color=background_color,
                width=250,
                height=250
            )
        )

        self.copy_button = Button(
            text="Copy",
            style=Pack(
                color=color,
                background_color=button_color,
                font_size = 12
            ),
            on_press=self.copy_qr_clipboard
        )

        self.save_button = Button(
            text="Save",
            style=Pack(
                color=color,
                background_color=button_color,
                font_size = 12
            ),
            on_press=self.save_qr
        )

        self.share_button = Button(
            text="Share",
            style=Pack(
                color=color,
                background_color=button_color,
                font_size = 12
            ),
            on_press=self.share_qr
        )

        self.qr_buttons = Box(
            style=Pack(
                direction = ROW,
                background_color = background_color,
                flex = 1,
                alignment = CENTER,
                padding = (5,0,0,0)
            )
        )

        self.qr_box = Box(
            style=Pack(
                direction = COLUMN,
                background_color=background_color,
                flex = 1,
                alignment = CENTER,
                padding = (15,0,0,0)
            )
        )
        self.qr_box.add(
            self.qr_view,
            self.qr_buttons
        )
        self.qr_buttons.add(
            self.copy_button,
            self.save_button,
            self.share_button
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
        if self.qr_view.image:
            self.qr_view.image = None
            self.widgets_box.remove(self.qr_box)

        beep = self.beep_switch.value
        torch = self.torch_switch.value
        asyncio.ensure_future(self.handle_scan(beep, torch))


    async def handle_scan(self, beep, torch):
        self._result = None
        context = MainActivity.singletonThis.getApplicationContext()
        result = await self._qr_scanner.start_scan(beep, torch, 15)

        if result == "__TIMEOUT__":
            Toast.makeText(context, "The scanner was timeout", Toast.LENGTH_SHORT).show()

        elif result:
            self._result = result
            self._qr_image = self.qr_generate()
            if self._qr_image:
                self.qr_view.image = self._qr_image
                self.widgets_box.insert(2, self.qr_box)
        else:
            Toast.makeText(context, "No result", Toast.LENGTH_SHORT).show()


    def qr_generate(self):
        import qrcode  
        qr_filename = f"qr_{self._result}.png"
        qr_path = os.path.join(self.app.paths.cache, qr_filename)
        if os.path.exists(qr_path):
            return qr_path
        
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=7,
            border=1,
        )
        qr.add_data(self._result)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        with open(qr_path, 'wb') as f:
            qr_img.save(f)
        
        return qr_path
    

    def copy_qr_clipboard(self, button):
        context = MainActivity.singletonThis.getApplicationContext()
        clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE)
        clipboard_manager = cast(ClipboardManager, clipboard)
        clip = ClipData.newPlainText("QR Code", self._result)
        clipboard_manager.setPrimaryClip(clip)
        Toast.makeText(context, "Copied to clipboard", Toast.LENGTH_SHORT).show()


    async def save_qr(self, button):
        context = MainActivity.singletonThis.getApplicationContext()
        folder_uri_str = await self.folder_picker.pick_folder()

        if not folder_uri_str:
            Toast.makeText(context, "No folder selected", Toast.LENGTH_SHORT).show()
            return
        if not self._qr_image or not os.path.exists(self._qr_image):
            Toast.makeText(context, "No QR image to save", Toast.LENGTH_SHORT).show()
            return
        try:
            folder_uri = Uri.parse(folder_uri_str)
            folder_doc = DocumentFile.fromTreeUri(context, folder_uri)

            if folder_doc is None or not folder_doc.canWrite():
                Toast.makeText(context, "Cannot write to selected folder", Toast.LENGTH_SHORT).show()
                return

            filename = os.path.basename(self._qr_image)
            existing = folder_doc.findFile(filename)
            if existing:
                existing.delete()

            mime_type = "image/png"
            new_file = folder_doc.createFile(mime_type, filename)
            if new_file is None:
                Toast.makeText(context, "Failed to create file", Toast.LENGTH_SHORT).show()
                return
            resolver = context.getContentResolver()
            output_stream = resolver.openOutputStream(new_file.getUri())
            input_stream = FileInputStream(self._qr_image)
            buffer = bytearray(4096)
            length = input_stream.read(buffer)
            while length > 0:
                output_stream.write(buffer, 0, length)
                length = input_stream.read(buffer)

            input_stream.close()
            output_stream.close()
            Toast.makeText(context, f"Saved to {filename}", Toast.LENGTH_SHORT).show()
        except Exception as e:
            Toast.makeText(context, f"Error saving file: {e}", Toast.LENGTH_LONG).show()
            print("Error:", e)


    def share_qr(self, button):
        if not self._qr_image:
            context = MainActivity.singletonThis.getApplicationContext()
            Toast.makeText(context, "No QR image to share", Toast.LENGTH_SHORT).show()
            return

        self.share_file.share(self._qr_image, mime_type="image/png", chooser_title="Share QR Code")


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
        version = "1.2.0"
    )
    app.main_loop()

if __name__ == "__main__":
    main()
