; Instalador do D3 Companion (Inno Setup 6). Quem roda é o ferramentas/empacotar.py:
;   ISCC.exe /DVersao=1.0.0 /DPasta=dist\D3 Companion /DSaida=dist /DIcone=build\icone.ico instalador.iss
; Instala só pra pessoa (sem pedir administrador) em %LOCALAPPDATA%\Programs\D3 Companion,
; com atalho no Menu Iniciar (e na Área de Trabalho, se marcar) e "Desinstalar"
; nas Configurações do Windows. As builds, o histórico e os prints ficam em
; %APPDATA%\D3 Companion: desinstalar não apaga (reinstalar acha tudo de volta).

#define Nome "D3 Companion"

[Setup]
; Nunca trocar o AppId: é por ele que o Windows sabe que a versão nova atualiza a velha.
AppId={{33F05C11-9D31-4E25-873E-D13D13F57021}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher=Ruthraaz
AppPublisherURL=https://ruthraaz.github.io/d3-companion/
AppSupportURL=https://github.com/Ruthraaz/d3-companion/issues
AppUpdatesURL=https://github.com/Ruthraaz/d3-companion/releases
DefaultDirName={localappdata}\Programs\{#Nome}
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir={#Saida}
OutputBaseFilename=D3-Companion-Setup-{#Versao}
SetupIconFile={#Icone}
UninstallDisplayIcon={app}\{#Nome}.exe
UninstallDisplayName={#Nome}
LicenseFile={#Pasta}\LICENSE.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Fecha o app aberto antes de atualizar (senão os arquivos estão em uso).
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Pasta}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Nome}.exe"
Name: "{group}\{cm:UninstallProgram,{#Nome}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#Nome}"; Filename: "{app}\{#Nome}.exe"; Tasks: atalho

[Run]
Filename: "{app}\{#Nome}.exe"; Description: "{cm:LaunchProgram,{#Nome}}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
; Atualizando: tira o _internal da versão velha antes (o PyInstaller muda nomes de arquivos).
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
; Restos da versão anterior que o instalador não conhece (o PyInstaller muda nomes).
Type: filesandordirs; Name: "{app}\_internal"
