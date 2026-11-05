; Fhoe-Rail Installer Script (Inno Setup)
; 参照 VS Code code.iss：WizardStyle=modern，纯脚本无外部 DLL。
; 用户可选：命令行版 / WebUI 版（[Components]），标准安装 / 绿色版（[Tasks]），
; 注册表关联与快捷方式按需勾选。构建：ISCC.exe installer.iss（tag 时由 CI 编译）。
; 依赖：仓库根 dist\Fhoe-Rail\（PyInstaller 产物）。

#define MyAppName "Fhoe-Rail"
; 版本号由 CI 通过 /DMyAppVersion=... 传入（来自 git tag），本地默认 4.6.0
#ifndef MyAppVersion
  #define MyAppVersion "4.6.0"
#endif
#define MyAppPublisher "Fhoe-Rail"
#define MyAppURL "https://github.com/linruowuyin/Fhoe-Rail"
#define MyAppExeName "Fhoe-Rail.exe"
#define MyWebUIExeName "Start-WebUI.exe"

[Setup]
AppId={{75e03832-2a99-4f65-9d9e-dae2bde329fb}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=Fhoe-Rail-Setup-{#MyAppVersion}
SetupIconFile=..\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
TimeStampsInUTC=yes
ShowLanguageDialog=auto
ChangesAssociations=no
UninstallDisplayName={#MyAppName}
UninstallFilesDir={app}\Uninstaller

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

; 许可协议（GPL-3.0 + 免责声明，取自 README「许可与免责声明」）
LicenseFile=..\installer\LICENSE.txt

[Types]
Name: "full"; Description: "{cm:TypeFull}"
Name: "custom"; Description: "{cm:TypeCustom}"

[Components]
; cli = 命令行版核心（主程序 + 库 + 地图/图片 + bat + 说明），必装不可取消
Name: "cli"; Description: "{cm:CompCLI}"; Types: full custom; Flags: fixed
; webui = WebUI 控制面板（启动器 + 独立库 + webui/ 目录），可选，默认装
Name: "webui"; Description: "{cm:CompWebUI}"; Types: full custom; ExtraDiskSpaceRequired: 0

[Tasks]
; 安装模式：标准（写注册表+快捷方式）或 绿色（纯文件）
Name: "normal"; Description: "{cm:TaskNormal}"; GroupDescription: "{cm:GroupMode}"; Flags: unchecked exclusive
Name: "portable"; Description: "{cm:TaskPortable}"; GroupDescription: "{cm:GroupMode}"; Flags: unchecked exclusive
; 快捷方式（仅标准安装时显示）
Name: "startmenu"; Description: "{cm:TaskStartMenu}"; GroupDescription: "{cm:GroupShortcut}"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:GroupShortcut}"; Flags: unchecked
; 注册表关联（仅标准安装时显示）
Name: "regassoc"; Description: "{cm:TaskRegAssoc}"; GroupDescription: "{cm:GroupOther}"; Flags: unchecked

[Files]
; 命令行版：dist\Fhoe-Rail\ 全部，排除 WebUI 专属文件（归 webui 组件）
Source: "..\dist\Fhoe-Rail\*"; DestDir: "{app}"; Components: cli; \
  Excludes: "{#MyWebUIExeName};launcher_libraries"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
; 数据目录（地图/图片/注意事项）随命令行版
Source: "..\map\*"; DestDir: "{app}\map"; Components: cli; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\picture\*"; DestDir: "{app}\picture"; Components: cli; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\新图注意事项\*"; DestDir: "{app}\新图注意事项"; Components: cli; Flags: ignoreversion recursesubdirs createallsubdirs
; 命令行版 bat 与说明
Source: "..\自选地图.bat"; DestDir: "{app}"; Components: cli; Flags: ignoreversion
Source: "..\录制地图.bat"; DestDir: "{app}"; Components: cli; Flags: ignoreversion
Source: "..\Fhoe-Rail.bat"; DestDir: "{app}"; Components: cli; Flags: ignoreversion
Source: "..\menu.txt"; DestDir: "{app}"; Components: cli; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Components: cli; Flags: ignoreversion
; WebUI 版：启动器 + 独立库 + webui/ 目录
Source: "..\dist\Fhoe-Rail\{#MyWebUIExeName}"; DestDir: "{app}"; Components: webui; Flags: ignoreversion
Source: "..\dist\Fhoe-Rail\launcher_libraries\*"; DestDir: "{app}\launcher_libraries"; Components: webui; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\webui\*"; DestDir: "{app}\webui"; Components: webui; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 快捷方式仅在标准安装 + 对应勾选时创建
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; \
  Tasks: normal and startmenu
Name: "{group}\{#MyAppName} WebUI"; Filename: "{app}\{#MyWebUIExeName}"; WorkingDir: "{app}"; \
  Tasks: normal and startmenu; Components: webui
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; \
  Tasks: normal and desktopicon
Name: "{autodesktop}\{#MyAppName} WebUI"; Filename: "{app}\{#MyWebUIExeName}"; WorkingDir: "{app}"; \
  Tasks: normal and desktopicon; Components: webui

[Registry]
; 注册表关联仅在标准安装 + 勾选时写入（App Paths + 卸载显示）
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallDir"; \
  ValueData: "{app}"; Tasks: normal and regassoc; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; \
  ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; \
  Tasks: normal and regassoc; Flags: uninsdeletekey

[Run]
; 安装完成后可选运行命令行版主程序
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
