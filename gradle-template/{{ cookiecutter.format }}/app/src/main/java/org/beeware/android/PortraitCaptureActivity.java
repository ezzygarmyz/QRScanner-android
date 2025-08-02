
package org.beeware.android;

import android.content.pm.ActivityInfo;
import android.os.Bundle;

import com.journeyapps.barcodescanner.CaptureActivity;


// By default, the CaptureActivity from the com.journeyapps.barcodescanner library (based on ZXing) starts the scanner in landscape mode.
// This forces the screen to stay in portrait mode while scanning the QR code.

public class PortraitCaptureActivity extends CaptureActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
    }
}
