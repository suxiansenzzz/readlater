package com.readlater.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;
    private LinearLayout loadingView;
    private LinearLayout errorView;
    private TextView tvErrorMessage;
    private TextView tvErrorDetail;

    private final Handler handler = new Handler(Looper.getMainLooper());

    // 服务器地址配置
    private static final String SERVER_URL = "http://192.168.31.5:8000";

    // Track whether main page has loaded successfully at least once
    private boolean hasMainPageLoaded = false;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 全屏显示
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );

        // Set window background to match splash color to prevent white flash
        getWindow().getDecorView().setBackgroundColor(Color.parseColor("#6366f1"));
        getWindow().setBackgroundDrawableResource(R.color.splash_background);

        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);
        progressBar = findViewById(R.id.progressBar);
        loadingView = findViewById(R.id.loadingView);
        errorView = findViewById(R.id.errorView);
        tvErrorMessage = findViewById(R.id.tvErrorMessage);
        tvErrorDetail = findViewById(R.id.tvErrorDetail);

        // Set WebView background to match splash (prevents white flash)
        webView.setBackgroundColor(Color.parseColor("#6366f1"));

        // WebView基本配置
        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);
        webSettings.setLoadWithOverviewMode(true);
        webSettings.setUseWideViewPort(true);
        webSettings.setBuiltInZoomControls(true);
        webSettings.setDisplayZoomControls(false);
        webSettings.setSupportZoom(true);
        webSettings.setCacheMode(WebSettings.LOAD_DEFAULT);

        // 启用混合内容（支持HTTPS和HTTP）
        webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        // 设置用户代理，标识为Android APP
        String userAgent = webSettings.getUserAgentString();
        webSettings.setUserAgentString(userAgent + " ReadLater-Android/1.0.3");

        // 启用Cookie
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        // 设置WebViewClient
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();

                // 处理外部链接
                if (!url.startsWith(SERVER_URL)) {
                    if (url.startsWith("data:") || url.startsWith("about:")) {
                        return false;
                    }
                    Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    startActivity(intent);
                    return true;
                }
                return false;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                progressBar.setVisibility(View.GONE);

                // Inject APP info into the loaded page
                injectAppInfo();

                // Dismiss loading overlay with 300ms delay to ensure rendering
                handler.postDelayed(() -> {
                    loadingView.setVisibility(View.GONE);
                }, 300);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);

                // Only handle errors for the main frame
                if (request != null && !request.isForMainFrame()) {
                    return;
                }

                // Only show error if we haven't successfully loaded the main page yet
                if (!hasMainPageLoaded) {
                    String description = (error != null) ? String.valueOf(error.getDescription()) : "Unknown error";
                    showErrorView(description);
                }
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse errorResponse) {
                super.onReceivedHttpError(view, request, errorResponse);

                // Only handle main frame HTTP errors
                if (request != null && !request.isForMainFrame()) {
                    return;
                }

                // Only show error page for serious HTTP errors (5xx, 4xx on main page)
                if (!hasMainPageLoaded) {
                    int statusCode = (errorResponse != null) ? errorResponse.getStatusCode() : 0;
                    if (statusCode >= 400) {
                        showErrorView("HTTP Error: " + statusCode);
                    }
                }
            }
        });

        // 设置WebChromeClient，处理进度条
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                super.onProgressChanged(view, newProgress);
                if (newProgress == 100) {
                    progressBar.setVisibility(View.GONE);
                }
            }
        });

        // 设置下载监听器
        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition,
                                        String mimetype, long contentLength) {
                Intent intent = new Intent(Intent.ACTION_VIEW);
                intent.setData(Uri.parse(url));
                startActivity(intent);
            }
        });

        // Retry button click handler
        findViewById(R.id.btnRetry).setOnClickListener(v -> retryConnection());

        // Start loading
        webView.loadUrl(SERVER_URL);
    }

    /**
     * Show the error view (native Android view, NOT HTML in WebView).
     * Hides WebView completely.
     */
    private void showErrorView(String error) {
        // Hide WebView - no error HTML loaded
        webView.setVisibility(View.GONE);

        // Hide loading overlay
        loadingView.setVisibility(View.GONE);

        // Cancel any pending dismiss handlers
        handler.removeCallbacksAndMessages(null);

        // Update error message text
        if (tvErrorDetail != null) {
            tvErrorDetail.setText(error);
        }

        // Show native error view
        errorView.setVisibility(View.VISIBLE);
    }

    /**
     * Retry connection - hide error view, show WebView, reload URL
     */
    private void retryConnection() {
        // Hide error view
        errorView.setVisibility(View.GONE);

        // Show WebView
        webView.setVisibility(View.VISIBLE);

        // Show loading overlay
        loadingView.setVisibility(View.VISIBLE);

        // Reset flag so next error can show
        hasMainPageLoaded = false;

        // Reload URL
        webView.loadUrl(SERVER_URL);
    }

    /**
     * 注入APP信息到网页
     */
    private void injectAppInfo() {
        if (webView == null) return;

        String js = "try { " +
            "window.ReadLaterApp = {" +
            "platform: 'android'," +
            "version: '1.0.3'," +
            "isApp: true" +
            "}; } catch(e) {}";
        webView.evaluateJavascript(js, null);

        // Mark that main page has loaded successfully
        hasMainPageLoaded = true;
    }

    // 处理返回键
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            // If error view is showing, go back to loading the server
            if (errorView.getVisibility() == View.VISIBLE) {
                retryConnection();
                return true;
            }
            if (webView != null && webView.canGoBack()) {
                webView.goBack();
                return true;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    // 处理系统返回手势
    @Override
    public void onBackPressed() {
        // If error view is showing, go back to loading the server
        if (errorView.getVisibility() == View.VISIBLE) {
            retryConnection();
            return;
        }
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (webView != null) {
            webView.onPause();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.onResume();
        }
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
