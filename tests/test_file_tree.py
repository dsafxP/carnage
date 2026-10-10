"""Tests for the installed-files tree builder."""

from __future__ import annotations

import carnage.tui.widgets.browse.package_detail as detail_module


class _Config:
    expand = False


class _FakeNode:
    """Records add()/add_leaf() calls like a Textual TreeNode."""

    def __init__(self) -> None:
        self.branches: list[tuple[str, _FakeNode]] = []
        self.leaves: list[str] = []

    def add(self, label, expand: bool = False) -> _FakeNode:
        child = _FakeNode()
        self.branches.append((str(label), child))
        return child

    def add_leaf(self, label) -> None:
        self.leaves.append(str(label))


def _names(node: _FakeNode) -> list[str]:
    return [label for label, _ in node.branches] + node.leaves


def test_file_tree_groups_without_rescanning(monkeypatch) -> None:
    monkeypatch.setattr(detail_module, "get_config", lambda: _Config())

    contents = {
        "/usr/bin/vim": ["obj"],
        "/usr/bin/xxd": ["obj"],
        "/usr/share/vim/doc.txt": ["obj"],
        "/etc/vimrc": ["obj"],
        "/var/empty": ["dir"],
        "/usr/bin/link": ["sym"],
    }

    root = _FakeNode()
    detail_module._build_file_tree(root, "", contents)  # type: ignore

    top = _names(root)
    assert any("usr" in label for label in top)
    assert any("etc" in label for label in top)
    assert any("var" in label for label in top)

    usr = next(child for label, child in root.branches if "usr" in label)
    assert any("bin" in label for label, _ in usr.branches)
    assert any("share" in label for label, _ in usr.branches)

    # Empty dirs still render as branches, symlinks and files as leaves.
    var = next(child for label, child in root.branches if "var" in label)
    assert len(var.branches) == 1

    bin_node = next(child for label, child in usr.branches if "bin" in label)
    assert len(bin_node.leaves) == 3


def test_file_tree_scales_linearly(monkeypatch) -> None:
    """20k synthetic entries must build in well under a second."""
    import time

    monkeypatch.setattr(detail_module, "get_config", lambda: _Config())

    contents = {f"/usr/share/pkg/file{i:05d}.dat": ["obj"] for i in range(20000)}

    root = _FakeNode()
    start = time.monotonic()
    detail_module._build_file_tree(root, "", contents)  # type: ignore
    elapsed = time.monotonic() - start

    assert elapsed < 2.0
    assert len(root.branches) == 1
