% CARNAGE(1) | User Commands

# NAME
carnage - TUI front-end for Portage and eix

# SYNOPSIS
**carnage** [*OPTIONS*]

# DESCRIPTION
**carnage** is a text-based user interface (TUI) front-end for **Portage** and **eix**.  
Its goal is to centralize common Gentoo package management tasks in a unified, efficient, and user-friendly interface.

**carnage** is not meant to compete in feature completeness with the command line.  
It is dedicated to providing an intuitive browsing and inspection environment rather than replacing emerge or eix directly.

Internally, **carnage** integrates with Portage and eix, adding a backend for extended functionality and caching beyond what the command line provides.

eix is not strictly necessary, and carnage can function without it for every other feature unrelated to packages.

Since eix is used for several operations internally, having a remote cache is important to have all options available. Optimizing eix will accelerate carnage at the same time.

# OPTIONS
| Option              | Description                                                                |
|---------------------|----------------------------------------------------------------------------|
| -h, \-\-help        | Show help message and exit.                                                |
| -V, \-\-version     | Show version information and exit.                                         |
| -c, \-\-config FILE | Path to configuration file.                                                |
| -\-css              | Path to custom Textual CSS file. Defaults to ~/.config/carnage/custom.tcss |

# CONFIGURATION
A default configuration file is automatically generated at: ~/.config/carnage/carnage.toml

It is automatically reset to default when a key is missing or is unparseable.

The file uses the [TOML](https://toml.io/) format and contains the following sections and options:

## [global]

| Key               | Type   | Description                                                                                                            | Default        |
|-------------------|--------|------------------------------------------------------------------------------------------------------------------------|----------------|
| theme             | string | User interface theme name. Recommended to change through the UI.                                                       | "textual-dark" |
| privilege_backend | string | Backend for privilege escalation when administrative commands are needed. **Options:** auto, pkexec, sudo, doas, none. | "auto"         |
| initial_tab       | string | Tab selected when starting Carnage. **Options:** news, glsas, browse, use, overlays.                                   | "news"         |
| compact_mode      | bool   | Reduce visual spacing for higher density.                                                                              | false          |
| ignore_warnings   | bool   | Suppress warnings.                                                                                                     | false          |
| terminal          | array  | Terminal to execute actions with. Useful to check output. Leave empty to execute as a subprocess.                      | []             |

## [browse]

| Key                | Type   | Description                                                             | Default       |
|--------------------|--------|-------------------------------------------------------------------------|---------------|
| search_flags       | array  | Default flags passed to eix during package search.                      | ["-f", "2"]   |
| minimum_characters | int    | Minimum number of characters before initiating search.                  | 3             |
| syntax_style       | string | Pygments style to use for ebuild syntax highlighting.                   | "github-dark" |
| expand             | bool   | Expand all tree nodes automatically in dependencies or installed files. | true          |
| depth              | int    | Dependency tree depth limit.                                            | 1             |

**Package search in the "Browse" tab supports searching flags directly.**  
For example, searching for \-\-installed will display all installed packages, ignoring search_flags defined in the configuration.

## [overlays]

| Key                    | Type   | Description                                        | Default                                            |
|------------------------|--------|----------------------------------------------------|----------------------------------------------------|
| skip_package\_counting | bool   | Skip counting packages for faster overlay loading. | true                                               |
| cache_max\_age         | int    | Maximum overlay cache age (hours).                 | 72                                                 |
| overlay_source         | string | URL to fetch overlay metadata.                     | "https://api.gentoo.org/overlays/repositories.xml" |

## [use]

| Key                | Type | Description                                       | Default |
|--------------------|------|---------------------------------------------------|---------|
| minimum_characters | int  | Minimum characters before USE flag search starts. | 3       |
| cache_max\_age     | int  | Maximum USE flag cache age (hours).               | 96      |

# BINDINGS
Bindings are available for each button in a tab.

## News

| Key | Description                 |
|-----|-----------------------------|
| r   | Mark selected news as read. |
| a   | Mark all news as read.      |
| p   | Purge all read news.        |

## Browse

| Key | Description                                         |
|-----|-----------------------------------------------------|
| e   | Emerge (install) selected package.                  |
| c   | Depclean (uninstall) selected package.              |
| w   | Deselect (remove from @world set) selected package. |
| n   | Don't replace (add to @world set) selected package. |

## Overlays

| Key | Description                            |
|-----|----------------------------------------|
| r   | Remove selected overlay.               |
| s   | Enable and then sync selected overlay. |

# SEE ALSO
**emerge**(1), **eix**(1), **portage**(5)
