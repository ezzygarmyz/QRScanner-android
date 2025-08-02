
from java import dynamic_proxy
from org.beeware.android import MainActivity, IPythonApp

from toga import App, MainWindow, Box, Label, Button
from toga.style.pack import Pack
from toga.constants import COLUMN, CENTER, BOLD
from toga.colors import rgb, WHITE, GREEN


class PythonAppProxy(dynamic_proxy(IPythonApp)):
    def __init__(self):
        super().__init__()

        self._back_callback = None
        self._qr_callback = None

    def set_onbackpressed_callback(self, callback):
        if callable(callback):
            self._back_callback = callback
        else:
            raise ValueError("Callback must be callable")
        
    def set_qr_callback(self, callback):
        if callable(callback):
            self._qr_callback = callback
        else:
            raise ValueError("QR callback must be callable")

    def onBackPressed(self):
        if self._back_callback:
            try:
                result = self._back_callback()
                if isinstance(result, bool):
                    return result
            except Exception as e:
                print("Back callback error:", e)
        return False
    
    def startQRScan(self):
        MainActivity.singletonThis.startQRScan()

    def onQRScanned(self, contents):
        if self._qr_callback:
            try:
                self._qr_callback(contents)
            except Exception as e:
                print("QR callback error:", e)



class BitcoinZGUI(MainWindow):
    def __init__(self):
        super().__init__()

        version = self.app.version
        self.app.proxy.set_qr_callback(self.on_qr_scanned)

        self.main_box = Box(
            style=Pack(
                direction = COLUMN,
                background_color=rgb(40,43,48),
                flex = 1,
                alignment = CENTER
            )
        )

        self.app_version = Label(
            text=f"v {version}",
            style=Pack(
                color = WHITE,
                background_color =rgb(40,43,48),
                flex = 1,
                text_align = CENTER,
                font_size=15,
                font_weight=BOLD,
                padding = (20,0,30,0)
            )
        )

        self.scan_button = Button(
            text="Scan QR",
            style=Pack(
                color = WHITE,
                background_color = GREEN,
                font_size = 14,
                alignment = CENTER,
                padding= (10,10,5,10)
            ),
            on_press=self.scan_qr
        )

        self.content = self.main_box
        self.main_box.add(
            self.scan_button,
            self.app_version
        )


    
    def scan_qr(self, button):
        self.app.proxy.startQRScan()


    def on_qr_scanned(self, contents):
        self.main_window.info_dialog(
            title="QR Code Scanned",
            message=f"Result :\n{contents}"
        )



class BitcoinZWallet(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.proxy = PythonAppProxy()
        self.proxy.set_onbackpressed_callback(self.on_back_pressed)


    def startup(self):
        MainActivity.setPythonApp(self.proxy)
        self.main_window = BitcoinZGUI()
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
    app = BitcoinZWallet(
        formal_name = "QRScanner",
        app_id = "com.qrscanner",
        home_page = "https://example.com",
        author = "BTCZCommunity",
        version = "1.0.0"
    )
    app.main_loop()

if __name__ == "__main__":
    main()
