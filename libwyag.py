"""
Parses command-line arguments
"""
import argparse

"""
Reads + writes config files.
"""
import configparser

from datetime import datetime

"""
Read the users/group database on Unix (`grp` is for groups, `pwd` for users)
because git saves the numerical owner/group ID of files and we want to display
that nicely (as text).
"""
try:
    import grp, pwd
except ModuleNotFoundError:
    pass # These modules are not available on Windows

"""
To support `.gitignore`, we'll need to match filenames against patterns like *.txt.
Filename mathc is in... `fnmatch`:
"""
from fnmatch import fnmatch

"""
Git uses the SHA-1 function quite extensively. In Python, it's in hashlib.
"""
import hashlib

from math import ceil
import os
import re
import sys

"""
Git compresses everything using zlib. Python has that, too.
"""
import zlib

argparser = argparse.ArgumentParser(description="The stupidest content tracker")

"""
We'll need to handle subcommands (as in git: `init`, `commit`, etc.) In argparse slang, these
are called "subparsers". At this point we only need to declare that our CLI will use some, and
that all invocation will actually require one - you don't just call `git`, you call `git COMMAND`.
"""
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

"""
The `dest="command"` argument states that the name of the chosen subparser will be returned as a
string in a field called `command`. So we just need to read this string and call the correct 
function accordingly. By convention, I'll call these functions "bridges functions" and prefix their 
names by `cmd_`. Bridge functions take the parsedd arguments as their unique parameter, and are 
responsible for processing and validating them before executing the actual command.
"""
def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    match args.command:
        case "add"          : cmd_add(args)
        case "cat-file"     : cmd_cat_file(args)
        case "check-ignore" : cmd_check_ignore(args)
        case "checkout"     : cmd_checkout(args)
        case "commit"       : cmd_commit(args)
        case "hash-object"  : cmd_hash_object(args)
        case "init"         : cmd_init(args)
        case "log"          : cmd_log(args)
        case "ls-files"     : cmd_ls_files(args)
        case "ls-tree"      : cmd_ls_tree(args)
        case "rev-parse"    : cmd_rev_parse(args)
        case "rm"           : cmd_rm(args)
        case "show-ref"     : cmd_show_ref(args)
        case "status"       : cmd_status(args)
        case "tag"          : cmd_tag(args)
        case _              : print("Bad command.")
