# Notes

## Ch.3 Creating repositories: init

- git repo = work tree + git directory
    - work tree = stores files
    - git directory = stores Git metadata (its own data)
- git repo file system structure:
```
/{worktree_folder}
    /.git
        config
```

## Ch.5 Reading commit history: log

- git commit = SHA-1 hash value of (
    tree object + 
    0 or more parents +
    author (name & email) & timestamp +
    commiter (name & emaiL) & timestamp +
    optional PGP signature +
    message
)
