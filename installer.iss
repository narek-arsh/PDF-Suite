; Instalador de PDF Manager by Provecto (Inno Setup 6)
; Compilar con:  ISCC.exe installer.iss   (antes: pyinstaller PDF.spec --noconfirm)

#define AppName "PDF Manager"
#define AppVersion "1.0.0"
#define AppPublisher "Provecto"
#define AppURL "https://provecto.app"
#define AppExe "PDFManager.exe"

[Setup]
AppId={{A1219086-54CA-49DA-A044-C3BF96F4B609}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL=https://github.com/provecto-app/PDF-Manager/issues
AppUpdatesURL=https://github.com/provecto-app/PDF-Manager/releases
DefaultDirName={autopf}\PDF Manager
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Instala solo para el usuario (sin pedir administrador); el asistente permite elegir «para todos».
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=LICENSE
SetupIconFile=provecto_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=installer_output
OutputBaseFilename=PDFManager-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\PDFManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
