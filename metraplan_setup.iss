; =====================================================================
; Métraplan — Script d'installation Inno Setup
; Version : 1.0.1
; Auteur  : M.Housse
; =====================================================================

#define AppName      "Métraplan"
#define AppVersion   "1.0.1"
#define AppPublisher "M.Housse"
#define AppURL       "https://www.metraplan.com"
#define AppExeName   "Metraplan.exe"

[Setup]
; Identifiant unique — NE PAS CHANGER entre les versions (pour les mises à jour)
AppId={{8B3F2A1C-4D7E-4F9A-B2C3-D1E5F6A7B8C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\Metraplan
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Icône de l'installateur
SetupIconFile=assets\icons\metraplan.ico
; Image de bienvenue (bannière gauche 164x314 px)
WizardImageFile=assets\images\setup_banner.bmp
; Petite image en haut à droite (55x58 px)
WizardSmallImageFile=assets\images\setup_small.bmp
OutputDir=dist
OutputBaseFilename=MetraplanInstall_v{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
; Niveau de privilèges : admin recommandé pour Program Files
PrivilegesRequired=admin
; Informations légales
LicenseFile=
; Signature numérique (décommenter après avoir signé)
; SignTool=signtool
WizardStyle=modern
; Empêcher plusieurs instances
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon";    Description: "Créer une icône sur le &bureau";       GroupDescription: "Icônes supplémentaires :"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Créer une icône dans la barre de &lancement rapide"; GroupDescription: "Icônes supplémentaires :"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
; Exécutable principal
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Fichier de configuration
Source: "config.ini";          DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

; Assets (images, icônes, styles) — exclure les fichiers de travail internes
Source: "assets\images\splash.png";        DestDir: "{app}\assets\images";  Flags: ignoreversion
Source: "assets\images\*.pdf";             DestDir: "{app}\assets\images";  Flags: ignoreversion skipifsourcedoesntexist
Source: "assets\icons\*";      DestDir: "{app}\assets\icons";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\style\*";      DestDir: "{app}\assets\style";   Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Raccourci dans le menu Démarrer
Name: "{group}\{#AppName}";                  Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icons\metraplan.ico"
Name: "{group}\Désinstaller {#AppName}";     Filename: "{uninstallexe}"

; Raccourci bureau (si coché)
Name: "{autodesktop}\{#AppName}";            Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icons\metraplan.ico"; Tasks: desktopicon

; Barre de lancement rapide (si coché)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
; Proposer de lancer l'application à la fin de l'installation
Filename: "{app}\{#AppExeName}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Supprimer les fichiers générés par l'application lors de la désinstallation
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\build"
