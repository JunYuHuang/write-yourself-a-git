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

"""
...`hash-object` converts an existing file into a git object, and `cat-file`
prints an existing git object to the standard output.

...you don't modify a file in git, you create a new file in a different 
location. [Git] Objects are just that: files in the git repository, whose paths
are determined by their contents.

Because it computes keys from data, Git would rather be called a value-value store.

How git stores objects:
1. object contents -> SHA-1 hash function -> hash-value
2. directory name = hash-value[0..2]
3. file name = hash-value[3..-1]

Object storage format = header + contents
- header = object type + space char + size + null
- object types: `blob`, `commit`, `tag`, `tree`
- e.g., |commit 1086.tree|
    - header type = `commit`
    - space char = ` `
    - object size = 1086 Bytes
    - null = `.`
    - start of object content = `tree`
- object headers and contents are compressed with `zlib`
"""

class GitObject (object):

    def __init__(self, data=None):
        if data != None:
            self.deserialize(data)
        else:
            self.init()
    
    def serialize(self, repo):
        """
        This function MUST be implemented by subclasses.
        It must read the object's contents from self.data, a byte string,
        and do whatever it takes to convert it into a meaningful representation.
        What exactly that means depend on each subclass.
        """
        raise Exception("Unimplemented!")
    
    def deserialize(self, data):
        raise Exception("Unimplemented!")

    def init(self):
        pass # Just do nothing. This is a reasonable default!

"""
Object reading pipeline:
-> object
-> SHA-1 hash function
-> object hash-value
-> path = `hash-value[0..2]/hash-value[3..-1]`
-> read path as binary file
-> decompress path via `zlib`
    -> object type -> use correct subclass
    -> object size -> recorded size equals real size?
-> create object from file opened from path
"""
def object_read(repo, sha):
    """
    Read object sha from Git repository repo. Return a GitObject
    whose exact type depends on the object.
    """

    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None

    with open (path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception(f"Malformed object {sha}: bad length")

        # Pick constructor
        match fmt:
            case b'commit'  : c=GitCommit
            case b'tree'    : c=GitTree
            case b'tag'     : c=GitTag
            case b'blob'    : c=GitBlob
            case _:
                raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")
        
        # Call constructor and return object
        return c(raw[y+1:])

"""
Writing an object is reading it in reverse: we compute the hash, insert the header, 
zlib-compress everything and write the result in the correct location. This really
shouldn't require much explanation, just notice that the hash is computed after the
header is added (so it's the hash of the object iself, uncompressed, not just its
contents).
"""
def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # Add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        # Compute path
        path=repo_path(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            with open(path, 'wb') as f:
                # Compress and write
                f.write(zlib.compress(result))
    return sha

"""
Blobs are unformatted, unspecified user data (e.g., `main.c`, `logo.png`, etc.).
Creating a `GitBlob` class is thus trivial, the `serialize`and `deserialize` functions
just have to store and return their input unmodified.
"""
class GitBlob(GitObject):
    fmt=b'blob'

    def serialize(self):
        return self.blobdata

    def serialize(self, data):
        self.blobdata = data

"""
`git cat-file` simply prints the raw contents of an object to stdout, uncompressed
and without the git header.

Our simplified version will ust take those two position arguments: a type and an 
object identifier:
```
wyag cat-file TYPE OBJECT
```
"""
argsp = argsubparsers.add_parser(
    "cat-file",
    help="Provide content of repository objects"
)

argsp.add_argument(
    "type",
    metavar="type",
    choices=["blob", "commit", "tag", "tree"],
    help="Specify the type"
)

argsp.add_argument(
    "object",
    metavar="object",
    help="The object to display"
)

def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encoed())

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())

"""
The reason for this strange small function is that Git has a lot of ways to
refer to objects: full hash, short hash, tags...`object_find()` will be our name
resolution function. We'll only implement it later, so this is just a temporary
placeholder. This means that until we implement the real thing, the only way we can
refer to an object will be by its full hash.
"""
def object_find(repo, name, fmt=None, follow=True):
    return name

"""
`hash-object`is basically the opposite of `cat-file`: it reads a file, computes its 
hash as an object, either storing it in the repository (if the -w flag is passed) or
just printing its hash.

The syntax of `wyag hash-object`is a simplification of `git hash-object`:
```
wyag hash-object [-w] [-t TYPE] FILE
```
"""
argsp = argsubparsers.add_paser(
    "hash-object",
    help="Compute object ID and optionally creates a blob from a file"
)

argsp.add_argument(
    "-t",
    metavar="type",
    dest="type",
    choices=["blob", "commit", "tag", "tree"],
    default="blob",
    help="Specify the type"
)

argsp.add_argument(
    "-w",
    dest="write",
    action="store_true",
    help="Actually write the object into the database"
)

argsp.add_argument(
    "path",
    help="Read object from <file>"
)

"""
A small bridge function.
"""
def cmd_hash_object(args):
    if args.write:
        repo = repo_find()
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)

def object_hash(fd, fmt, repo=None):
    """
    Hash object, writing it to repo if provided.
    """
    data = fd.read()

    # Choose constructor according to fmt argment
    match fmt:
        case b'commit'  : obj=GitCommit(data)
        case b'tree'    : obj=GitTree(data)
        case b'tag'     : obj=GitTag(data)
        case b'blob'    : obj=GitBlob(data)
        case _: raise Exception(f"Unknown type {fmt}!")

    return object_write(obj, repo)

"""
KVLM = Key-Value List with Message.
Used for parsing both `commit` and `tag` git object types because 
they have the same format.

Use dicts / hashmaps to store key/value association + rely on preserved insertion order (a Python dictionary feature). Why?
- Git rule: same name refers to same object
- Git rule: same object referred to by same name

Git assumes 2 tree objects w/ unlike names are different.
"""
def kvlm_parse(raw, start=0, dct=None):
    if not dct:
        dct = dict()
        # You CANNOT delcare the argument as dct=dict() or all call to
        # the functions will endlessly grow the same dict.

    # This function is recursive: it reads a key/value pair, then call
    # itself back with the new position. So we first need to know where
    # we are: at a keyword, or already in the messageQ

    # We search for the next space and the next newline.
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)

    # If space appears before newline, we have a keyword. Otherwise,
    # it's the final message, whichj we just read to the end of the file.

    # Base case
    # =========
    # If newline appears first (or there's no space at all, in which case
    # find returns -1), we assume a blank line. A blank line means the 
    # remainder of the data is the message. We store it in the dictionary,
    # with None as they key, and return.
    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start+1:]
        return dct

    # Recursive case
    # ==============
    # we read a key-value pair and recurse for the next.
    key = raw[start:spc]

    # Find the end of the value. Continuation lines begin with a
    # space, so we loop until we find a "\n" not followed by a space.
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' ' ): break

    # Grab the value
    # Also, drop the leading space on continuation lines
    value = raw[spc+1:end].replace(b'\n', b'\n')

    # Don't overwrite existing data contents
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [ dct[key], value ]
    else:
        dct[key]=value

    return kvlm_parse(raw, start=end+1, dct=dct)

"""
Write all fields first, then a newline, the message, and a final newline.
"""
def kvlm_serialize(kvlm):
    ret = b''

    # Output fields
    for k in kvlm.keys():
        # Skip the message itself
        if k == None: continue
        val = kvlm[k]
        # Normalize to a list
        if type(val) != list:
            val = [ val ]

        for v in val:
            ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'

    # Append message
    ret += b'\n' + kvlm[None]

    return ret

class GitCommit(GitObject):
    fmt=b'commit'

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)

    def serialize(self):
        return kvlm_serialize(self.kvlm)

    def init(self):
        self.kvlm = dict()

"""
We'll dump Graphviz data and let the user use `dot` to render the actual log.
"""
argsp = argsubparsers.add_parser(
    "log",
    help="Display history of a given commit."
)
argsp.add_argument(
    "commit",
    default="HEAD",
    nargs="?",
    help="Commit to start at."
)

def cmd_log(args):
    repo = repo_find()

    print("digraph wyaglog{")
    print("  node[shape=rectl]")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")

def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    message = commit.kvlm[None].decode("utf8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace("\"", "\\\"")

    if "\n" in message: # Keep only the first line
        message = message[:message.index("\n")]

    printf(f"  c_{sha} [label=\"{sha[0:7]}: {message}\"]")
    assert commit.fmt==b'commit'

    if not b'parent' in commit.kvlm.keys():
        # Base case: the initial commit.
        return
    
    parents = commit.kvlm[b'parent']

    if type(parents) != list:
        parents = [ parents ]

    for p in parents:
        p = p.decode("ascii")
        print(f"  c_{sha} -> c_{p};")
        log_graphviz(repo, p, seen)

