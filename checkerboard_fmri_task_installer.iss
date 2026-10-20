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
; Generated from assets/ by build.ps1; the uninstall entry reuses the exe's embedded icon.
SetupIconFile=build_output\checkerboard_fmri_task.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; Tells Explorer to refresh its icon cache after install; otherwise a reinstall over the same
; path keeps showing the old cached shortcut icon.
ChangesAssociations=yes
; Close anything holding the files open before overwriting them (Inno 6's default, stated
; explicitly); don't relaunch user-started tools afterwards.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; task_config.toml is replaced on every install; [Code] first backs up the previous copy to
; task_config.previous.toml (not installed by Inno, so the uninstaller leaves it alone).
Source: "build_output\payload\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Icons]
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userdesktop}\{#MyAppName} config"; Filename: "notepad.exe"; Parameters: """{app}\task_config.toml"""; Tasks: desktopicon
Name: "{userdesktop}\{#MyAppName} data"; Filename: "{code:GetDataDir}"; Tasks: desktopicon

[Code]
var
  DataDirPage: TInputDirWizardPage;

// Where the task saves its logs. Pre-filled (last install's choice, else Documents), so
// clicking Next -- or a /SILENT install -- keeps the default.
procedure InitializeWizard();
begin
  DataDirPage := CreateInputDirPage(wpSelectDir,
    'Select Data Folder', 'Where should session logs be saved?',
    'Each session''s event log and a copy of its settings are saved in this folder. ' +
    'The default suits most PCs.' + #13#10#13#10 +
    'If Windows Security''s "Controlled folder access" is on, Documents may be blocked: ' +
    'choose a folder outside it (for example D:\fmri_data).',
    False, '');
  DataDirPage.Add('');
  DataDirPage.Values[0] := GetPreviousData('DataDir',
    ExpandConstant('{userdocs}\checkerboard_fmri_task'));
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'DataDir', DataDirPage.Values[0]);
end;

function GetDataDir(Param: String): String;
begin
  Result := DataDirPage.Values[0];
end;

// Same check the task makes at start-up: create the folder and write a throwaway file.
function DataDirWritable(const Dir: String): Boolean;
var
  TestFile: String;
begin
  Result := False;
  if not ForceDirectories(Dir) then
    exit;
  TestFile := AddBackslash(Dir) + 'write_test.tmp';
  if SaveStringToFile(TestFile, 'write test', False) then
  begin
    DeleteFile(TestFile);
    Result := True;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = DataDirPage.ID) and not DataDirWritable(DataDirPage.Values[0]) then
    Result := MsgBox('Setup could not write to:' + #13#10 + DataDirPage.Values[0] + #13#10#13#10 +
      'Use this folder anyway? Choose No to pick another one. ' +
      'The task checks the folder again each time it starts.',
      mbConfirmation, MB_YESNO) = IDYES;
end;

// Points the freshly installed task_config.toml's [output] data_dir at the chosen folder.
// The shipped file is ASCII-only, so reading it back here can't garble any characters.
procedure SetConfigDataDir(Dir: String);
var
  ConfigPath: String;
  Lines: TArrayOfString;
  I: Integer;
begin
  ConfigPath := ExpandConstant('{app}\task_config.toml');
  if not LoadStringsFromFile(ConfigPath, Lines) then
    exit;
  // Forward slashes: backslashes would be escape characters in a TOML string.
  StringChangeEx(Dir, '\', '/', True);
  for I := 0 to GetArrayLength(Lines) - 1 do
    if Pos('data_dir =', Lines[I]) = 1 then
      Lines[I] := 'data_dir = "' + Dir + '"    # set by the installer [default: ""]';
  SaveStringsToUTF8File(ConfigPath, Lines, False);
end;

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

// Keeps the user's edited settings recoverable before the new default config replaces them.
procedure BackUpConfig();
var
  ConfigPath: String;
begin
  ConfigPath := ExpandConstant('{app}\task_config.toml');
  if FileExists(ConfigPath) then
    FileCopy(ConfigPath, ExpandConstant('{app}\task_config.previous.toml'), False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    BackUpConfig();
    if IsUpgrade() then
      UninstallOldVersion();
  end;
  if CurStep = ssPostInstall then
    SetConfigDataDir(GetDataDir(''));
end;
