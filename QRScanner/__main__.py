
import asyncio
import time
import os

from java import dynamic_proxy, cast, jclass
from java.util import Arrays
from java.lang import Runnable
from java.io import FileInputStream, File
from android.app import AlertDialog
from android.net import Uri
from android.view import KeyEvent
from android.content import Intent, Context, ClipData, ClipboardManager, DialogInterface
from android.widget import Toast, EditText
from android.text import InputType
from android.graphics import Color
from android.graphics.drawable import ColorDrawable
from android.content.res import Configuration
from androidx.core.content import FileProvider
from androidx.documentfile.provider import DocumentFile
from androidx.activity.result import ActivityResultCallback
from com.journeyapps.barcodescanner import ScanOptions, ScanContract
from org.beeware.android import MainActivity, IPythonApp, PortraitCaptureActivity

from toga import App, MainWindow, Box, Label, Button, Switch, ImageView
from toga.style.pack import Pack
from toga.constants import COLUMN, CENTER, BOLD, ROW
from toga.colors import rgb, WHITE


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
    def __init__(self, activity):
        self.activity = activity
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
    def __init__(self, activity):
        self.context = activity.getApplicationContext()
        self.package_name = self.context.getPackageName()
        self.fileprovider_authority = f"{self.package_name}.fileprovider"

    def share(self, file_path: str, mime_type="image/*", chooser_title="Share Qr Code"):
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
    def __init__(self, activity):
        self.activity = activity
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



class DialogClickListener(dynamic_proxy(DialogInterface.OnClickListener)):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def onClick(self, dialog, which):
        self.callback(dialog, which)


class DialogKeyListener(dynamic_proxy(DialogInterface.OnKeyListener)):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def onKey(self, dialog, keyCode, event):
        return self.callback(dialog, keyCode, event)
    

class DialogCancelListener(dynamic_proxy(DialogInterface.OnCancelListener)):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def onCancel(self, dialog):
        self.callback(dialog)



class InputDialog:
    def __init__(self, activity):
        self.activity = activity
        self._future = None

    async def get_input(self, title:str=None, hint:str=None, input_type:str=None):
        self._future = asyncio.get_event_loop().create_future()
        self.activity.runOnUiThread(RunnableProxy(lambda: self._show_dialog(title, hint, input_type)))
        return await self._future

    def _show_dialog(self, title, hint, input_type):
        edit_text = EditText(self.activity)

        if input_type == "number":
            edit_text.setInputType(InputType.TYPE_CLASS_NUMBER)
        elif input_type == "password":
            edit_text.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD)
        elif input_type == "email":
            edit_text.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS)
        else:
            edit_text.setInputType(InputType.TYPE_CLASS_TEXT)

        edit_text.setHint(hint)

        config = self.activity.getResources().getConfiguration()
        is_dark = (config.uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES

        if is_dark:
            bg_color = Color.GRAY
            text_color = Color.WHITE
            hint_color = Color.LTGRAY
            button_text_color = Color.WHITE
        else:
            bg_color = Color.WHITE
            text_color = Color.BLACK
            hint_color = Color.DKGRAY
            button_text_color = Color.BLACK

        edit_text.setBackgroundColor(bg_color)
        edit_text.setTextColor(text_color)
        edit_text.setHintTextColor(hint_color)

        dialog_builder = AlertDialog.Builder(self.activity)
        dialog_builder.setTitle(title)
        dialog_builder.setView(edit_text)

        positive_listener = DialogClickListener(lambda dialog, which: self._set_result(edit_text.getText().toString()))
        negative_listener = DialogClickListener(lambda dialog, which: self._set_result(None))

        dialog_builder.setPositiveButton("Confirm", positive_listener)
        dialog_builder.setNegativeButton("Cancel", negative_listener)
        dialog_builder.setCancelable(True)

        dialog = dialog_builder.create()

        dialog.getWindow().setBackgroundDrawable(ColorDrawable(bg_color))

        key_listener = DialogKeyListener(
            lambda dialog, keyCode, event: self._handle_back(dialog, keyCode, event)
        )
        dialog.setOnKeyListener(key_listener)
        dialog.setOnCancelListener(DialogCancelListener(lambda dialog: self._set_result(None)))
        dialog.show()

        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(button_text_color)
        dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(button_text_color)

    def _handle_back(self, dialog, keyCode, event):
        if keyCode == KeyEvent.KEYCODE_BACK:
            self._set_result(None)
            dialog.dismiss()
            return True
        return False

    def _set_result(self, result):
        if self._future and not self._future.done():
            self._future.set_result(result or "")



class QRScannerGUI(MainWindow):
    def __init__(self):
        super().__init__()

        self.activity = MainActivity.singletonThis
        self.context = self.activity.getApplicationContext()
        version = self.app.version
        self._qr_scanner = QRScanner(self.activity)
        self.folder_picker = FolderPicker(self.activity)
        self.share_file = FileShare(self.activity)

        self._qr_image = None

        theme = self.is_dark_theme()
        text_color = WHITE
        if theme == "dark":
            background_color = rgb(40,43,48)
            button_color = rgb(66,69,73)
            switch_color = rgb(30,33,36)
        else:
            background_color = rgb(0,133,119)
            button_color = rgb(0,87,75)
            switch_color = rgb(0,87,75)

        x = self.screen_size()
        qr_width = x - 150

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
                color = text_color,
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
                color = text_color,
                background_color = switch_color,
                font_size = 14,
                padding= (15,20,5,20)
            )
        )

        self.beep_switch = Switch(
            text="Beep :",
            value=False,
            style=Pack(
                color = text_color,
                background_color = switch_color,
                font_size = 14,
                padding= (10,20,15,20)
            )
        )
        
        self.stwitchs_box = Box(
            style=Pack(
                direction = COLUMN,
                background_color= switch_color
            )
        )
        self.stwitchs_box.add(
            self.torch_switch,
            self.beep_switch
        )

        self.qr_view = ImageView(
            style=Pack(
                background_color=background_color,
                width=qr_width
            )
        )

        self.copy_button = Button(
            icon="icons/copy",
            style=Pack(
                background_color=button_color,
                font_size = 12,
                padding = (0,15,0,0)
            ),
            on_press=self.copy_qr_clipboard
        )

        self.save_button = Button(
            icon="icons/save",
            style=Pack(
                background_color=button_color,
                font_size = 12,
                padding = (0,15,0,0)
            ),
            on_press=self.save_qr
        )

        self.share_button = Button(
            icon="icons/share",
            style=Pack(
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
                color = text_color,
                background_color = button_color,
                font_size = 14,
                alignment = CENTER,
                padding= (15,10,5,10)
            ),
            on_press=self.scan_qr
        )

        self.generate_button = Button(
            text="Generate QR",
            style=Pack(
                color = text_color,
                background_color = button_color,
                font_size = 14,
                alignment = CENTER,
                padding= (15,10,5,10)
            ),
            on_press=self.text_to_qr
        )

        self.content = self.main_box
        self.main_box.add(
            self.widgets_box,
            self.app_version
        )
        self.widgets_box.add(
            self.stwitchs_box,
            self.scan_button,
            self.generate_button
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
        result = await self._qr_scanner.start_scan(beep, torch, 15)

        if result == "__TIMEOUT__":
            Toast.makeText(self.context, "The scanner was timeout", Toast.LENGTH_SHORT).show()

        elif result:
            self._result = result
            self._qr_image = self.qr_generate()
            if self._qr_image:
                self.qr_view.image = self._qr_image
                self.widgets_box.insert(2, self.qr_box)
        else:
            Toast.makeText(self.context, "No result", Toast.LENGTH_SHORT).show()


    async def text_to_qr(self, button):
        if self.qr_view.image:
            self.qr_view.image = None
            self.widgets_box.remove(self.qr_box)

        dialog = InputDialog(self.activity)
        result = await dialog.get_input(title="Generate QR", hint="Enter a text for this QR", input_type="text")
        if result:
            self._result = result
            self._qr_image = self.qr_generate()
            if self._qr_image:
                self.qr_view.image = self._qr_image
                self.widgets_box.insert(2, self.qr_box)
        else:
            Toast.makeText(self.context, "Input cancelled", Toast.LENGTH_SHORT).show()


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
        clipboard = self.context.getSystemService(Context.CLIPBOARD_SERVICE)
        clipboard_manager = cast(ClipboardManager, clipboard)
        clip = ClipData.newPlainText("QR Code", self._result)
        clipboard_manager.setPrimaryClip(clip)
        Toast.makeText(self.context, "Copied to clipboard", Toast.LENGTH_SHORT).show()


    async def save_qr(self, button):
        folder_uri_str = await self.folder_picker.pick_folder()

        if not folder_uri_str:
            Toast.makeText(self.context, "No folder selected", Toast.LENGTH_SHORT).show()
            return
        if not self._qr_image or not os.path.exists(self._qr_image):
            Toast.makeText(self.context, "No QR image to save", Toast.LENGTH_SHORT).show()
            return
        try:
            folder_uri = Uri.parse(folder_uri_str)
            folder_doc = DocumentFile.fromTreeUri(self.context, folder_uri)

            if folder_doc is None or not folder_doc.canWrite():
                Toast.makeText(self.context, "Cannot write to selected folder", Toast.LENGTH_SHORT).show()
                return

            filename = os.path.basename(self._qr_image)
            existing = folder_doc.findFile(filename)
            if existing:
                existing.delete()

            mime_type = "image/png"
            new_file = folder_doc.createFile(mime_type, filename)
            if new_file is None:
                Toast.makeText(self.context, "Failed to create file", Toast.LENGTH_SHORT).show()
                return
            resolver = self.context.getContentResolver()
            output_stream = resolver.openOutputStream(new_file.getUri())
            input_stream = FileInputStream(self._qr_image)
            buffer = bytearray(4096)
            length = input_stream.read(buffer)
            while length > 0:
                output_stream.write(buffer, 0, length)
                length = input_stream.read(buffer)

            input_stream.close()
            output_stream.close()
            Toast.makeText(self.context, f"Saved to {filename}", Toast.LENGTH_SHORT).show()
        except Exception as e:
            Toast.makeText(self.context, f"Error saving file: {e}", Toast.LENGTH_LONG).show()
            print("Error:", e)


    def share_qr(self, button):
        if not self._qr_image:
            Toast.makeText(self.context, "No QR image to share", Toast.LENGTH_SHORT).show()
            return

        self.share_file.share(self._qr_image, mime_type="image/png", chooser_title="Share QR Code")


    def is_dark_theme(self):
        try:
            config = self.context.getResources().getConfiguration()
            ui_mode = config.uiMode
            is_dark = (ui_mode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
            return "dark" if is_dark else "light"
        except Exception as e:
            print("Theme detection failed:", e)
            return "unknown"
        

    def screen_size(self):
        for secreen in self.app.screens:
            width = secreen.size.width

        return width



class QRScannerExample(App):
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
    app = QRScannerExample(
        formal_name = "QRScanner",
        app_id = "com.qrscanner",
        home_page = "https://example.com",
        author = "BTCZCommunity",
        version = "1.3.0"
    )
    app.main_loop()

if __name__ == "__main__":
    main()
