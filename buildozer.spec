[app]

# Buildozer Documentation
# https://github.com/Android-for-Python/Android-for-Python-Users/blob/main/README.md


#pre-splace screen
#presplash.filename = resources/images/splash.png

#app icon
#icon.filename = resources/images/icon.png

# (str) Title of your application
title = bSPP

# (str) Package name
package.name = bSPP

# (str) Package domain (needed for android/ios packaging)
package.domain = org.sarahroslives

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,conf,ttf,ini,csv

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests, bin, test_scripts

# Android Permissions https://developer.android.com/reference/android/Manifest.permission
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, BLUETOOTH, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION
#android.wakelock = True

# (str) Application versioning (method 1)
version = 0.0.2

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3, kivy==2.3.0, https://files.pythonhosted.org/packages/20/81/0b1154f5e581d5910702d9fadb3217f56cb186f72c8b36de0271e7ff9b5c/kivymd-1.2.0.tar.gz, bleak, typing_extensions
#p4a.branch = develop

# (str) Supported orientation (landscape, portrait, etc)
orientation = portrait

fullscreen = 0