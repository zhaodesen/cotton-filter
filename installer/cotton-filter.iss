#define AppName "cotton-filter"
#ifndef AppVersion
#define AppVersion "dev"
#endif

[Setup]
AppId={{7C0B4D58-0F21-4C54-88AE-6F3C09B8DE9E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=zhaodesen
AppPublisherURL=https://github.com/zhaodesen/cotton-filter
AppSupportURL=https://github.com/zhaodesen/cotton-filter/issues
AppUpdatesURL=https://github.com/zhaodesen/cotton-filter/releases/latest
DefaultDirName={localappdata}\Programs\cotton-filter
DefaultGroupName=cotton-filter
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=cotton-filter-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\cotton-filter.exe
SetupIconFile=..\assets\icon.ico

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\cotton-filter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\cotton-filter"; Filename: "{app}\cotton-filter.exe"
Name: "{userdesktop}\cotton-filter"; Filename: "{app}\cotton-filter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\cotton-filter.exe"; Description: "{cm:LaunchProgram,cotton-filter}"; Flags: nowait postinstall skipifsilent
