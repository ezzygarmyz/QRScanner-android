
package org.beeware.android;

import android.app.Activity;
import android.util.Log;

import java.util.Arrays;
import com.journeyapps.barcodescanner.ScanOptions;
import com.journeyapps.barcodescanner.ScanContract;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

import com.chaquo.python.PyObject;

public class QRScanner {

    private final Activity activity;
    private final ActivityResultLauncher<ScanOptions> scanLauncher;

    public QRScanner(Activity activity) {
        this.activity = activity;

        this.scanLauncher = ((MainActivity) activity).registerForActivityResult(
            new ScanContract(),
            result -> {
                if (result.getContents() != null) {
                    String contents = result.getContents();
                    Log.d("QRScanner", "Scanned QR Code: " + contents);

                    // callback to python
                    PyObject pythonApp = MainActivity.getPythonApp();
                    if (pythonApp != null && pythonApp.containsKey("onQRScanned")) {
                        pythonApp.callAttr("onQRScanned", contents);
                    }
                }
            }
        );
    }

    public void startScan() {
        ScanOptions options = new ScanOptions();
        options.setPrompt("Scan a QR Code");
        options.setBeepEnabled(true); // (false) to disable beep sound
        options.setCaptureActivity(PortraitCaptureActivity.class);
        options.setDesiredBarcodeFormats(Arrays.asList("QR_CODE")); // if only for QR Code
        // 
        // options.setDesiredBarcodeFormats(ScanOptions.ALL_CODE_TYPES);
        // available formats :
        //   "AZTEC","CODABAR","CODE_39","CODE_93","CODE_128","DATA_MATRIX","EAN_8","EAN_13","ITF"
        //   "MAXICODE","PDF_417","QR_CODE","RSS_14","RSS_EXPANDED","UPC_A","UPC_E","UPC_EAN_EXTENSION"
        scanLauncher.launch(options);
    }
}

