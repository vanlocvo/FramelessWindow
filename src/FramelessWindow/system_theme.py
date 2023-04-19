import winreg

class SYSTEMTHEME:
    IsDarkTheme = False
    AccentColor = 'rgb(0, 120, 215)'

    @classmethod
    def Update(cls):
        path_theme = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        name_theme = r"AppsUseLightTheme"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_theme) as registry_key:
            value, regtype = winreg.QueryValueEx(registry_key, name_theme)
            cls.IsDarkTheme = not bool(value)

        path_accent = r'SOFTWARE\\Microsoft\Windows\\CurrentVersion\\Explorer\\Accent'
        name_accent =   r"AccentColorMenu"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_accent) as registry_key:
            value, regtype = winreg.QueryValueEx(registry_key, name_accent)
            accent = value - 4278190080
            accent = str(hex(accent)).split('x')[1]
            accent = accent[4:6]+accent[2:4]+accent[0:2]
            accent = 'rgb'+str(tuple(int(accent[i:i+2], 16) for i in (0, 2, 4)))
            cls.AccentColor = accent