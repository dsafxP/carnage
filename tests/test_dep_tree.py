"""Tests for the dependency tree built from graph_depends() output."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Tree

import carnage.tui.widgets.browse.package_detail as detail_module
from carnage.tui.widgets.browse.package_detail import _build_dep_tree


class _Config:
    """Stand-in for Configuration so the tests never touch the real file."""

    expand = True
    depth = 1


class _TreeHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield Tree("root", id="pkg-deps-tree")


@pytest.fixture(autouse=True)
def config_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detail_module, "get_config", lambda: _Config())


def _labels(node) -> list[str]:
    return [str(child.label) for child in node.children]


async def test_a_sibling_subtree_is_not_duplicated_under_the_next_sibling() -> None:
    deps = [(1, "app-a/a"), (2, "app-b/b"), (1, "app-d/d")]

    app = _TreeHarness()
    async with app.run_test():
        root = app.query_one(Tree).root
        _build_dep_tree(root, deps)

        # A and D are siblings; only A has a dependency, and it must not be
        # attached to D as well. Labels come back rendered, hence plain text.
        assert _labels(root) == ["app-a/a", "app-d/d"]
        assert _labels(root.children[0]) == ["app-b/b"]
        assert _labels(root.children[1]) == []


async def test_a_flat_depth_one_list_stays_flat() -> None:
    deps = [(1, "app-a/a"), (1, "app-b/b")]

    app = _TreeHarness()
    async with app.run_test():
        root = app.query_one(Tree).root
        _build_dep_tree(root, deps)

        assert len(root.children) == 2
        assert all(not child.children for child in root.children)


async def test_nested_children_stay_under_their_own_parent() -> None:
    deps = [(1, "a/a"), (2, "b/b"), (3, "c/c"), (1, "d/d"), (2, "e/e")]

    app = _TreeHarness()
    async with app.run_test():
        root = app.query_one(Tree).root
        _build_dep_tree(root, deps)

        assert _labels(root) == ["a/a", "d/d"]
        assert _labels(root.children[0]) == ["b/b"]
        assert _labels(root.children[0].children[0]) == ["c/c"]
        assert _labels(root.children[1]) == ["e/e"]
