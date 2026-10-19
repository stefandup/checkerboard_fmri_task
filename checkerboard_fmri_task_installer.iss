; Checkerboard fMRI Task installer.
; Built by build.ps1, which invokes: ISCC.exe checkerboard_fmri_task_installer.iss /DMyAppVersion=<version>

#define MyAppName "Checkerboard fMRI Task"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif
#define MyAppPublisher "Stellenbosch University"
#define MyAppURL "https://www.sun.ac.za"
#define MyAppExeName "checkerboard_fmri_task.exe"
#define MyAppId "68DACD3E-6650-4B99-BEA1-54C7EB0AF113"

[Setup]
; Three "{" here, not two: the preprocessor substitutes "{#MyAppId}" with the raw GUID text
; *before* Inno's own "{{" (literal "{") escaping is evaluated, so "{{#MyAppId}" collapses to
; one unescaped "{" with no closing "}" -- a compile error. "{{{#MyAppId}}" preprocesses to
; "{{<guid>}", which is what AppId needs.
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\CheckerboardFmriTask
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=CheckerboardFmriTaskSetup-{#MyAppVersion}
; Relative to this script's own directory (the repo root) -- keeps every build artifact
; under one gitignored build_output/ tree instead of a top-level Output/ folder.
OutputDir=build_output\installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Close anything holding the files open before overwriting them (Inno 6's default, stated
; explicitly); don't relaunch user-started tools afterwards.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "build_output\payload\*"; DestDir: "{app}"; Excludes: "task_config.toml"; Flags: ignoreversion recursesubdirs createallsubdirs
; The config holds the lab's verified settings: never overwrite or remove an edited copy
; (the upgrade step in [Code] runs the old uninstaller first, so uninsneveruninstall matters).
Source: "build_output\payload\task_config.toml"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Icons]
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userdesktop}\{#MyAppName} config"; Filename: "notepad.exe"; Parameters: """{app}\task_config.toml"""; Tasks: desktopicon

[Code]
// PrivilegesRequired=lowest -- this installer only ever writes its uninstall entry under
// HKCU, so that's the only hive a previous install of this same AppId could be under.
function GetUninstallString(): String;
var
  UninstallKey: String;
  UninstallString: String;
begin
  // {#MyAppId} preprocesses to the bare GUID (no braces) -- the registry key has them.
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{' + '{#MyAppId}' + '}_is1';
  if not RegQueryStringValue(HKCU, UninstallKey, 'QuietUninstallString', UninstallString) then
    RegQueryStringValue(HKCU, UninstallKey, 'UninstallString', UninstallString);
  Result := UninstallString;
end;

function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;

// QuietUninstallString is a full command line ('"<path>" /SILENT'), not a bare path. This
// pulls out just the quoted (or, lacking quotes, whole) path and drops any trailing arguments.
function ExtractExePath(const CommandLine: String): String;
var
  ClosingQuote: Integer;
begin
  if (Length(CommandLine) > 0) and (CommandLine[1] = '"') then
  begin
    ClosingQuote := Pos('"', Copy(CommandLine, 2, Length(CommandLine) - 1));
    if ClosingQuote > 0 then
    begin
      Result := Copy(CommandLine, 2, ClosingQuote - 1);
      exit;
    end;
  end;
  Result := CommandLine;
end;

// Runs the previous version's own uninstaller silently, so the new version's [Files] always
// lands in a clean directory -- files the new version no longer ships aren't left behind.
procedure UninstallOldVersion();
var
  UninstallString: String;
  ResultCode: Integer;
begin
  UninstallString := GetUninstallString();
  if UninstallString = '' then
    exit;
  UninstallString := ExtractExePath(UninstallString);
  Exec(UninstallString, '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if IsUpgrade() then
      UninstallOldVersion();
  end;
end;
