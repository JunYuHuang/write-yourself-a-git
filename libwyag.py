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

"""
To create a new `Repository` object, we only need to make a few checks:
- We must verify that the directory exists, and contains a subidrectory called `.git`.
- We then read its configuration in `.git/config` (it's just an INI file) and check that
`core.respositoryformatversion`is 0. More on that field in a moment.
"""
class GitRepository (object):
    """A git repository"""

    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion: {vers}")

"""
(A note on Python syntax: the star on the `*path` makes the function variadic, so it can be
called with multiple path components as separate arguments. For example,
`repo_path(repo, "objects", "df", "4ec9fc2ad990cb9da906a95a6eda6627d7b7b0")` is a valid call.
The function receives `path`as a list)
"""
def repo_path(repo, *path):
    """Compute path under repo's gitdir."""
    return os.path.join(repo.gitdir, *path)

"""
The next two functions, `repo_file()`and `reop_dir()`, return and optionally create a path
to a file or a directory respectively. The difference between them is that the file version
only creates directories up to the last component.
"""
def repo_file(repo, *path, mkdir=False):
    """
    Same as repo_path, but create dirname(*path) if absent. For example,
    `repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\")` will create 
    `.git/refs/remotes/origin`.
    """

    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
    """Same as `repo_path`, but mkdir *path if absent if mkdir."""

    path = repo_path(repo, *path)

    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception(f"Not a directory {path}")

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None

"""
To create a new repository, we start with a directory (which we create if it doesn't already
exist) and create the git directory inside (which must not exist already, or be empty). That
directory is called `.git` (the leading period makes it "hidden" on Unix systems), and contains:
- `.git/objects/`: the object store, which we'll introduce in the next section.
- `.git/refs/` the reference store, which we'll discuss a bit later. It contains two subdirectories,
`heads` and `tags`.
- `.git/HEAD`, a reference to the current `HEAD` (more on that later!)
- `.git/config`, the repository's configuration file.
- `.git/description`, holds a free-form description of this respository's contents, for humans, and
is rarely used.
"""
def repo_create(path):
    """Create a new repository at `path`."""

    repo = GitRepository(path, True)

    # First, we make sure the `path` either doesn't exist or is an
    # empty dir.

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception (f"{path} is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception (f"{path} is not empty!")
    else:
        os.makedirs(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # .git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("refL refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo

"""
The configuration file is very simple, it's a INI-like file with a single section
(`[core]`) and three fields:
- `repositoryformatversion = 0`: the version of the gitdir format. 0 means the 
initial format, 1 the same with extensions. If > 1, git will panic; wyag will only
accept 0.
- `filemode = false`: disable tracking of file modes (permissions) changes in the
work tree.
- `bare = false`: indicates that this repository has a worktree. Git supports an optional
`worktree` key which indicates the location of the worktree, if not `..`; wyag doesn't.

We create this file using Python's `configparser` lib:
"""
def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return set

"""
The syntax of `wyag init` is going to be:
```
wyag init [path]
```

We already have the complete repository creation logic. To create the command, we're
only going to need two more things:
1. We need to create an argparse subparser to handle our command's argument.
"""
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")

"""
In the case of `init`, there's a single, optional, positional argument: the path where
to init the repo. It defaults to `.`, the current directory:
"""
argsp.add_argument(
    "path",
    metavar="directory",
    nargs="?",
    default=".",
    help="Where to create the repository."
)

"""
2. We also need a "bridge" function that will read argument values from the object
returned by argparse and call the actual function with correct values.
"""
def cmd_init(args):
    repo_create(args.path)

"""
The `repo_find()` function we'll now create will look for that
root, starting at the current directory and recursing back to
`/`. To identify a path as a respository, it will check for the
presence of a `.git` directory.
"""
def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    # If we haven't returned, recurse in parent, if w
    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        # Bottom case
        # os.path.join("/", "..") == "/":
        # If parent==path, then path is root.
        if required:
            raise Exception("No git directory.")
        else:
            return None
    
    # Recursive case
    return repo_find(parent, required)
