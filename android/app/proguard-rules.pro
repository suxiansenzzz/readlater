# Proguard规则
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

-keepclassmembers class com.readlater.app.MainActivity$* {
    *;
}

-keepattributes JavascriptInterface
-keepattributes *Annotation*

# 保留WebView相关
-keep class android.webkit.** { *; }
-dontwarn android.webkit.**
