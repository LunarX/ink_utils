#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
import os
import pathlib
import shutil
import subprocess

import eml_writer as ew
import loco_updater as lu
import login as lg
from adb import adb, select_device, get_all_devices, close_app, open_app
from utils import remove_empty_items, select_in_list, accept_substitution


def clear_mail_db(args):
    if not (args.mailbox or args.mailbox_info or args.user or args.coil or args.network or args.everything):
        print("No target specified. Fallback on removing mailboxes")
        args.mailbox = True

    if args.all_devices:
        device_ids = get_all_devices()
    else:
        device_ids = [select_device()]

    for device_id in device_ids:
        if args.mailbox or args.everything:
            adb("exec-out run-as com.infomaniak.mail find ./files -name 'Mailbox-*-*.realm*' -exec rm -r {} \\;", device_id)

        if args.mailbox_info or args.everything:
            adb("exec-out run-as com.infomaniak.mail find ./files -name 'MailboxInfo.realm*' -exec rm -r {} \\;", device_id)

        if args.user or args.everything:
            adb("exec-out run-as com.infomaniak.mail find ./files -name 'User-*.realm*' -exec rm -r {} \\;", device_id)

        if args.coil or args.everything:
            adb("exec-out run-as com.infomaniak.mail find ./cache -name '*_cache' -exec rm -r {} \\;", device_id)

        if args.network or args.everything:
            adb("exec-out run-as com.infomaniak.mail find ./files -name 'network-response-body-*' -exec rm {} \\;", device_id)

        if args.restart:
            close_app(device_id)
            open_app(device_id)


def show_layout_bounds(args):
    device_id = select_device()

    result = adb("shell getprop debug.layout", device_id)
    print("When getting current prop state we get: [" + result.stdout.strip() + "]")
    new_layout_state = "false" if (result.stdout.strip() == "true") else "true"
    print("Setting show layout bounds to " + new_layout_state)
    adb("shell setprop debug.layout " + new_layout_state, device_id)
    adb("shell service call activity 1599295570", device_id)


def generate_eml(args):
    html = accept_substitution(args.html)
    ew.new_eml(args.subject, args.sender, args.to, args.cc, html)


def copy_last_video(args):
    device_id = select_device()

    root = pathlib.Path.home().__str__() + "/"
    desktop = "Desktop/"
    destination = root + desktop
    if args.here:
        destination = "./"

    movie_dir = "storage/emulated/0/Movies/"
    filename = adb("shell ls -tp " + movie_dir + " | grep -v /$ | head -1", device_id).stdout.strip()
    file = movie_dir + filename
    adb("pull " + file + " " + destination, device_id)
    print("Pulled " + filename + " successfully")

    if args.open:
        subprocess.Popen(("open", destination + filename), cwd=None)


def update_loco(args):
    if not args.check:
        lu.update_loco()
        print()

    print("Searching for errors in imported strings")
    error_count = lu.validate_strings()
    if error_count == 0:
        print("Found no error")
    else:
        accord = "s" if error_count > 1 else ""
        print(f"\nFound {error_count} error{accord}")


def login(args):
    lg.login(args.add, args.web)


def open_db(args):
    device_id = select_device()

    ls_files = "ls -lhS ./files"
    select_columns = "awk '{print $8, $5, $6, $7}'"
    keep_db = f"grep -x '{get_db_pattern(args)}'"

    result = adb(f"shell run-as com.infomaniak.mail {ls_files} | {select_columns} | {keep_db}", device_id)
    files = remove_empty_items(result.stdout.split("\n"))

    filename = select_in_list("Select database", files).split(" ")[0]

    working_directory = "/tmp/ink_db_pull/"
    if os.path.exists(working_directory):
        shutil.rmtree(working_directory)
    os.makedirs(working_directory, exist_ok=True)

    pull_local_file(f"./files/{filename}", f"{working_directory}/{filename}", device_id)

    subprocess.Popen(("open", working_directory + filename), cwd=None)


def get_db_pattern(args):
    if args.user:
        return "User-.*realm\s.*"
    elif args.mailbox_info:
        return "MailboxInfo.realm\s.*"
    else:
        return "Mailbox-.*realm\s.*"


def pull_local_dir(src_path, dest_path, device_id):
    result = adb(f"exec-out run-as com.infomaniak.mail ls -1 {src_path}", device_id)
    os.makedirs(dest_path, exist_ok=True)
    files = remove_empty_items(result.stdout.split("\n"))
    for file in files:
        pull_local_file(f"{src_path}/{file}", f"{dest_path}/{file}", device_id)


def pull_local_file(src_path, dest_path, device_id):
    adb(f"exec-out run-as com.infomaniak.mail cat '{src_path}' > {dest_path}", device_id)


def force_dark_mode(args):
    device_id = select_device()
    set_dark_mode("yes", device_id)


def force_light_mode(args):
    device_id = select_device()
    set_dark_mode("no", device_id)


def toggle_dark_light_mode(args):
    device_id = select_device()

    result = adb('shell "cmd uimode night"', device_id)

    is_night_mode_output = result.stdout.strip()
    start_index = is_night_mode_output.rindex(": ") + 2

    is_night_mode = is_night_mode_output[start_index:] == "yes"
    next_state = "no" if is_night_mode else "yes"

    set_dark_mode(next_state, device_id)


def set_dark_mode(yes_or_no, device_id):
    adb(f'shell "cmd uimode night {yes_or_no}"', device_id)


def extract_apk(args):
    optional_grep = "" if args.keyword is None else f" | grep {args.keyword}"
    find_packages_command = f"shell pm list packages -f{optional_grep}"

    device_id = select_device()
    raw_output = adb(find_packages_command, device_id).stdout.strip().splitlines()

    packages = []
    for line in raw_output:
        if line.__contains__("/base.apk="):
            packages.append(line.split("/base.apk=")[-1])

    selected_package = select_in_list("Choose package to extract", packages)

    download_apk_command = f"shell 'cat `pm path {selected_package} | cut -d':' -f2`' > {selected_package}.apk"
    adb(download_apk_command, device_id)

    print("Extraction finished")


def catch_empty_calls(parser):
    return lambda _: parser.print_usage()


def define_commands(parser):
    subparsers = parser.add_subparsers(help='sub-command help')

    # Databases
    db_parser = subparsers.add_parser("db", help="open or rm databases of the project")
    db_parser.set_defaults(func=catch_empty_calls(db_parser))
    db_subparser = db_parser.add_subparsers(help="db-sub-command help")
    db_clear_parser = db_subparser.add_parser("rm", help="deletes all of the databases containg mails or attachment "
                                                         "cache but keeps the account logged in using adb")
    db_clear_parser.add_argument("-r", "--restart", action="store_true", default=False,
                                 help="also restart the app")
    db_clear_parser.add_argument("-ad", "--all-devices", action="store_true", default=False,
                                 help="apply to all connected devices")
    db_clear_parser.add_argument("-m", "--mailbox", action="store_true", default=False,
                                 help="removes mailbox content databases")
    db_clear_parser.add_argument("-mi", "-i", "--mailbox-info", action="store_true", default=False,
                                 help="removes mailbox info databases")
    db_clear_parser.add_argument("-u", "--user", action="store_true", default=False,
                                 help="removes user info databases")
    db_clear_parser.add_argument("-c", "--coil", action="store_true", default=False,
                                 help="removes coil caches")
    db_clear_parser.add_argument("-n", "--network", action="store_true", default=False,
                                 help="removes network caches")
    db_clear_parser.add_argument("-e", "--everything", action="store_true", default=False,
                                 help="remove all of the possible files")
    db_clear_parser.set_defaults(func=clear_mail_db)
    db_open_parser = db_subparser.add_parser("open", help="pulls and open a db file")
    db_open_parser.add_argument("-u", "--user", action="store_true", default=False, help="open users databases")
    db_open_parser.add_argument("-mi", "-i", "--mailbox-info", action="store_true", default=False,
                                help="open mailbox info databases")
    db_open_parser.set_defaults(func=open_db)

    # Show layout bounds
    bounds_parser = subparsers.add_parser("bounds", help="toggles layout bounds for the android device using adb")
    bounds_parser.set_defaults(func=show_layout_bounds)

    # Eml
    eml_parser = subparsers.add_parser("eml", help="creates an eml file in the current directory")
    eml_parser.add_argument("html", nargs="?", help="html code of the content of the mail")
    eml_parser.add_argument("-s", "--subject", dest="subject", help="subject of the mail")
    eml_parser.add_argument("-f", "--from", dest="sender", help="sender of the mail. Comma separated if there's more "
                                                                "than one. To have a recipient with a name and an "
                                                                "email follow this pattern: name <email@domain.ext>")
    eml_parser.add_argument("-t", "--to", dest="to", help="recipient of the mail. Comma separated if there's more "
                                                          "than one")
    eml_parser.add_argument("-c", "--cc", dest="cc", help="recipient of a copy of the mail. Comma separated if "
                                                          "there's mor than one")
    eml_parser.set_defaults(func=generate_eml)

    # Open last video
    last_video_parser = subparsers.add_parser("lastvid",
                                              help="copies last recorded video of the emulator to the desktop")
    last_video_parser.add_argument("-o", "--open", action="store_true", default=False,
                                   help="opens the file in default player at the same time")
    last_video_parser.add_argument("--here", action="store_true", default=False,
                                   help="downloads the file in current directory instead of desktop")
    last_video_parser.set_defaults(func=copy_last_video)

    # Loco
    loco_parser = subparsers.add_parser("loco", help="automatically import loco and remove loco's autogenerated header")
    loco_parser.add_argument("-c", "--check", action="store_true", default=False,
                             help="only checks if strings in the project are correctly formatted but do not import")
    loco_parser.set_defaults(func=update_loco)

    # Login
    login_parser = subparsers.add_parser("login", help="automated the process of logging in")
    login_parser.add_argument("-a", "--add", action="store_true", default=False,
                              help="skip view pager four pages navigation when you add a new account to existing ones")
    login_parser.add_argument("-w", "--web", action="store_true", default=False,
                              help="start login inputs from the webview")
    login_parser.set_defaults(func=login)

    # Dark mode
    dark_mode_parser = subparsers.add_parser("color", help="changes dark and light mode")
    dark_mode_parser.set_defaults(func=catch_empty_calls(dark_mode_parser))
    color_subparser = dark_mode_parser.add_subparsers(help="db-sub-command help")
    dark_parser = color_subparser.add_parser("dark", help="sets dark mode")
    dark_parser.set_defaults(func=force_dark_mode)
    light_parser = color_subparser.add_parser("light", help="sets light mode")
    light_parser.set_defaults(func=force_light_mode)
    toggle_parser = color_subparser.add_parser("toggle", help="toggles the current dark mode")
    toggle_parser.set_defaults(func=toggle_dark_light_mode)

    # Apk extraction
    apk_extraction_parser = subparsers.add_parser("apk", help="extract an installed apk")
    apk_extraction_parser.add_argument("keyword", nargs="?", help="only propose package names that contains this given string")
    apk_extraction_parser.set_defaults(func=extract_apk)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()  # (description="Arguments for kmail")
    parser.set_defaults(func=catch_empty_calls(parser))

    define_commands(parser)

    # Actual parsing of the user input
    args = parser.parse_args()
    args.func(args)
