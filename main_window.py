# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Union, Any, Tuple
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFrame, QToolBar, QTextEdit, QMenuBar, QMenu, QStatusBar,
    QFileDialog, QMessageBox, QDockWidget, QTreeView, QTabWidget,
    QInputDialog, QLineEdit, QProgressDialog, QLabel, QComboBox,
    QCheckBox, QPushButton, QActionGroup, QDialog, QApplication
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QDir, QFileSystemModel, QTimer,
    QSettings, QSize, QPoint, QUrl, QModelIndex,
    QDragEnterEvent, QDropEvent, QEvent
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import (
    QAction, QIcon, QKeySequence, QFontDatabase,
    QTextCharFormat, QColor, QPalette, QTextCursor,
    QCloseEvent
)

# Import custom modules
from core.template_manager import TemplateManager
from core.project_manager import ProjectManager
from core.file_manager import FileManager
from core.settings_manager import SettingsManager
from core.html_parser import HTMLParser
from core.css_manager import CSSManager

from ui.dialogs import (
    SearchDialog, SettingsDialog, ValidationDialog,
    AccessibilityDialog, KeyboardShortcutsDialog,
    GitCommitDialog, NewProjectDialog, ProjectSettingsDialog,
    PreferencesDialog
)
from ui.editor.code_editor import CodeEditor
from ui.preview.preview_window import PreviewWindow

from utils.git_manager import GitManager, GitError
from utils.snippet_manager import SnippetManager
from utils.emmet_handler import EmmetHandler
from utils.accessibility_checker import AccessibilityChecker
from utils.syntax_highlighter import HTMLHighlighter, CSSHighlighter
from utils.validator import HTMLValidator


@dataclass
class AppConfig:
    """Application configuration"""
    NAME: str = "CloudWorks HTML Editor"
    VERSION: str = "1.0.0"
    TIMESTAMP: str = "2025-02-16 17:20:37"
    AUTHOR: str = "vcutrone"
    MIN_WINDOW_SIZE: Tuple[int, int] = (1024, 768)
    AUTO_SAVE_INTERVAL: int = 300  # 5 minutes
    MAX_RECENT_FILES: int = 10
    MAX_RECENT_PROJECTS: int = 5
    DEFAULT_ENCODING: str = "UTF-8"


class MainWindow(QMainWindow):
    """
    Main application window for CloudWorks HTML Editor

    Last modified: 2025-02-16 17:20:37
    Modified by: vcutrone
    """

    # Signal definitions with type hints
    projectOpened = pyqtSignal(str)  # Path of opened project
    projectClosed = pyqtSignal()  # No arguments
    fileOpened = pyqtSignal(str)  # Path of opened file
    fileSaved = pyqtSignal(str)  # Path of saved file
    themeChanged = pyqtSignal(str)  # Name of new theme

    def __init__(self):
        """Initialize the main window"""
        super().__init__()

        # Initialize state tracking
        self._initialize_state()

        # Initialize managers
        self._initialize_managers()

        # Setup UI components
        self._setup_ui()

        # Setup signal connections
        self._setup_connections()

        # Configure auto-save
        self._setup_auto_save()

        # Load and apply settings
        self._load_settings()

        # Set window properties
        self.setWindowTitle(AppConfig.NAME)
        self._update_status("Ready")

        logger.info(
            f"[{AppConfig.TIMESTAMP}] MainWindow initialized by {AppConfig.AUTHOR}"
        )

    def _initialize_state(self):
        """
        Initialize internal state variables

        Last modified: 2025-02-16 17:21:22
        Modified by: vcutrone
        """
        self.state = {
            'current_file': None,
            'current_project': None,
            'modified_files': set(),
            'recent_files': [],
            'recent_projects': [],
            'search_widget': None,
            'auto_save_timer': None,
            'last_save_time': datetime.now(),
            'current_theme': 'light',
            'is_maximized': False,
            'cursor_position': (1, 1),
            'view_mode': 'code',  # 'code', 'design', or 'split'
            'zoom_level': 100,
            'timestamp': "2025-02-16 17:21:22",
            'user': "vcutrone"
        }

        logger.debug(
            f"[{self.state['timestamp']}] State initialized by {self.state['user']}"
        )

    def _initialize_managers(self):
        """
        Initialize component managers

        Last modified: 2025-02-16 17:21:22
        Modified by: vcutrone
        """
        try:
            self.managers = {
                'template': TemplateManager(),
                'project': ProjectManager(),
                'file': FileManager(),
                'settings': SettingsManager(),
                'git': GitManager(),
                'snippet': SnippetManager(),
                'emmet': EmmetHandler(),
                'html': HTMLParser(),
                'css': CSSManager(),
                'validator': HTMLValidator(),
                'accessibility': AccessibilityChecker()
            }

            logger.info(
                f"[{self.state['timestamp']}] Managers initialized by "
                f"{self.state['user']}"
            )

        except Exception as e:
            logger.critical(
                f"[{self.state['timestamp']}] Failed to initialize managers: {str(e)}"
            )
            raise SystemExit("Failed to initialize application managers")

    def _setup_ui(self):
        """
        Initialize the main window UI components

        Last modified: 2025-02-16 17:21:22
        Modified by: vcutrone
        """
        try:
            # Set minimum window size
            self.setMinimumSize(*AppConfig.MIN_WINDOW_SIZE)

            # Create central widget and layout
            self._setup_central_widget()

            # Create menu bar and menus
            self._create_menus()

            # Create toolbars
            self._create_toolbars()

            # Create main content area
            self._create_main_content()

            # Create status bar
            self._create_status_bar()

            # Create dock widgets
            self._create_dock_widgets()

            # Apply theme
            self._apply_theme(
                self.managers['settings'].get_value("appearance/theme", "light")
            )

            logger.info(
                f"[{self.state['timestamp']}] UI setup completed by "
                f"{self.state['user']}"
            )

        except Exception as e:
            logger.critical(
                f"[{self.state['timestamp']}] Failed to setup UI: {str(e)}"
            )
            raise SystemExit("Failed to initialize application UI")

    def _setup_central_widget(self):
        """
        Setup central widget and main layout

        Last modified: 2025-02-16 17:21:22
        Modified by: vcutrone
        """
        try:
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)

            self.main_layout = QVBoxLayout(self.central_widget)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)

        except Exception as e:
            logger.error(
                f"[{self.state['timestamp']}] Failed to setup central widget: "
                f"{str(e)}"
            )
            raise

    def _create_status_bar(self):
        """
        Create enhanced status bar with additional information widgets

        Last modified: 2025-02-16 17:21:22
        Modified by: vcutrone
        """
        try:
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)

            # Create status widgets
            self.status_widgets = {
                'position': QLabel("Ln 1, Col 1"),
                'encoding': QLabel(AppConfig.DEFAULT_ENCODING),
                'syntax': QLabel("HTML"),
                'git': QLabel(),
                'zoom': QLabel("100%"),
                'selection': QLabel(),
                'modified': QLabel()
            }

            # Add widgets to status bar
            for widget in self.status_widgets.values():
                self.status_bar.addPermanentWidget(widget)

            # Initialize git status
            self._update_git_status()

            logger.debug(
                f"[{self.state['timestamp']}] Status bar created by "
                f"{self.state['user']}"
            )

        except Exception as e:
            logger.error(
                f"[{self.state['timestamp']}] Failed to create status bar: "
                f"{str(e)}"
            )
            raise

    def _create_menus(self):
        """
        Create main menu bar and all submenus

        Last modified: 2025-02-16 17:22:08
        Modified by: vcutrone
        """
        try:
            self.menubar = self._create_menu_bar()
            self.setMenuBar(self.menubar)

            # Create main menus
            self.menus = {
                'file': self._create_file_menu(),
                'edit': self._create_edit_menu(),
                'view': self._create_view_menu(),
                'project': self._create_project_menu(),
                'tools': self._create_tools_menu(),
                'help': self._create_help_menu()
            }

            # Add menus to menu bar
            for menu in self.menus.values():
                self.menubar.addMenu(menu)

            logger.debug(
                f"[{AppConfig.TIMESTAMP}] Menus created by {AppConfig.AUTHOR}"
            )

        except Exception as e:
            logger.error(f"Failed to create menus: {str(e)}")
            raise

    def _create_file_menu(self) -> QMenu:
        """
        Create File menu with all actions

        Returns:
            QMenu: Configured File menu
        """
        file_menu = QMenu("&File", self)

        # Define file actions with shortcuts
        actions = [
            {
                'name': 'new',
                'text': "&New",
                'shortcut': QKeySequence.StandardKey.New,
                'icon': "new.png",
                'slot': self._new_file,
                'status_tip': "Create a new file"
            },
            {
                'name': 'open',
                'text': "&Open...",
                'shortcut': QKeySequence.StandardKey.Open,
                'icon': "open.png",
                'slot': self._open_file,
                'status_tip': "Open an existing file"
            },
            None,  # Separator
            {
                'name': 'save',
                'text': "&Save",
                'shortcut': QKeySequence.StandardKey.Save,
                'icon': "save.png",
                'slot': self._save_file,
                'status_tip': "Save the current file"
            },
            {
                'name': 'save_as',
                'text': "Save &As...",
                'shortcut': QKeySequence.StandardKey.SaveAs,
                'icon': "save_as.png",
                'slot': self._save_file_as,
                'status_tip': "Save the current file with a new name"
            },
            {
                'name': 'save_all',
                'text': "Save A&ll",
                'shortcut': "Ctrl+Shift+S",
                'icon': "save_all.png",
                'slot': self._save_all_files,
                'status_tip': "Save all open files"
            },
            None,  # Separator
            {
                'name': 'export',
                'text': "&Export...",
                'shortcut': "Ctrl+E",
                'icon': "export.png",
                'slot': self._export_file,
                'status_tip': "Export the current file"
            },
            None,  # Separator
            {
                'name': 'exit',
                'text': "E&xit",
                'shortcut': QKeySequence.StandardKey.Quit,
                'icon': "exit.png",
                'slot': self.close,
                'status_tip': "Exit the application"
            }
        ]

        # Create and add actions
        self.file_actions = {}
        for action_def in actions:
            if action_def is None:
                file_menu.addSeparator()
                continue

            action = QAction(action_def['text'], self)

            if 'shortcut' in action_def:
                action.setShortcut(action_def['shortcut'])

            if 'icon' in action_def:
                icon_path = os.path.join("resources", "icons", action_def['icon'])
                if os.path.exists(icon_path):
                    action.setIcon(QIcon(icon_path))

            if 'slot' in action_def:
                action.triggered.connect(action_def['slot'])

            if 'status_tip' in action_def:
                action.setStatusTip(action_def['status_tip'])

            self.file_actions[action_def['name']] = action
            file_menu.addAction(action)

        # Add recent files submenu
        self.recent_files_menu = QMenu("Recent &Files", self)
        file_menu.insertMenu(self.file_actions['exit'], self.recent_files_menu)
        file_menu.insertSeparator(self.file_actions['exit'])

        # Update recent files list
        self._update_recent_files_menu()

        return file_menu

    def _create_edit_menu(self) -> QMenu:
        """
        Create Edit menu with all related actions

        Last modified: 2025-02-16 17:31:39
        Modified by: vcutrone

        Returns:
            QMenu: Configured Edit menu
        """
        edit_menu = QMenu("&Edit", self)

        # Define edit actions
        actions = [
            {
                'name': 'undo',
                'text': "&Undo",
                'shortcut': QKeySequence.StandardKey.Undo,
                'icon': "undo.png",
                'slot': lambda: self._get_current_editor().undo(),
                'status_tip': "Undo the last action"
            },
            {
                'name': 'redo',
                'text': "&Redo",
                'shortcut': QKeySequence.StandardKey.Redo,
                'icon': "redo.png",
                'slot': lambda: self._get_current_editor().redo(),
                'status_tip': "Redo the previously undone action"
            },
            None,  # Separator
            {
                'name': 'cut',
                'text': "Cu&t",
                'shortcut': QKeySequence.StandardKey.Cut,
                'icon': "cut.png",
                'slot': lambda: self._get_current_editor().cut(),
                'status_tip': "Cut the selected text to clipboard"
            },
            {
                'name': 'copy',
                'text': "&Copy",
                'shortcut': QKeySequence.StandardKey.Copy,
                'icon': "copy.png",
                'slot': lambda: self._get_current_editor().copy(),
                'status_tip': "Copy the selected text to clipboard"
            },
            {
                'name': 'paste',
                'text': "&Paste",
                'shortcut': QKeySequence.StandardKey.Paste,
                'icon': "paste.png",
                'slot': lambda: self._get_current_editor().paste(),
                'status_tip': "Paste text from clipboard"
            },
            None,  # Separator
            {
                'name': 'find',
                'text': "&Find...",
                'shortcut': QKeySequence.StandardKey.Find,
                'icon': "find.png",
                'slot': lambda: self._show_search(replace=False),
                'status_tip': "Find text in the current file"
            },
            {
                'name': 'replace',
                'text': "&Replace...",
                'shortcut': QKeySequence.StandardKey.Replace,
                'icon': "replace.png",
                'slot': lambda: self._show_search(replace=True),
                'status_tip': "Find and replace text in the current file"
            },
            None,  # Separator
            {
                'name': 'select_all',
                'text': "Select &All",
                'shortcut': QKeySequence.StandardKey.SelectAll,
                'icon': "select_all.png",
                'slot': lambda: self._get_current_editor().selectAll(),
                'status_tip': "Select all text in the current file"
            },
            None,  # Separator
            {
                'name': 'indent',
                'text': "&Indent",
                'shortcut': "Tab",
                'icon': "indent.png",
                'slot': self._indent_selection,
                'status_tip': "Indent the selected text"
            },
            {
                'name': 'unindent',
                'text': "&Unindent",
                'shortcut': "Shift+Tab",
                'icon': "unindent.png",
                'slot': self._unindent_selection,
                'status_tip': "Unindent the selected text"
            }
        ]

        # Create and add actions
        self.edit_actions = {}
        for action_def in actions:
            if action_def is None:
                edit_menu.addSeparator()
                continue

            action = self._create_action(action_def)
            self.edit_actions[action_def['name']] = action
            edit_menu.addAction(action)

        # Add advanced edit submenu
        advanced_menu = self._create_advanced_edit_menu()
        edit_menu.addSeparator()
        edit_menu.addMenu(advanced_menu)

        return edit_menu

    def _create_advanced_edit_menu(self) -> QMenu:
        """
        Create Advanced Edit submenu

        Last modified: 2025-02-16 17:31:39
        Modified by: vcutrone

        Returns:
            QMenu: Configured Advanced Edit submenu
        """
        advanced_menu = QMenu("Ad&vanced", self)

        # Define advanced edit actions
        actions = [
            {
                'name': 'comment',
                'text': "Toggle &Comment",
                'shortcut': "Ctrl+/",
                'icon': "comment.png",
                'slot': self._toggle_comment,
                'status_tip': "Toggle comment on selected lines"
            },
            {
                'name': 'format',
                'text': "&Format Document",
                'shortcut': "Ctrl+Shift+F",
                'icon': "format.png",
                'slot': self._format_document,
                'status_tip': "Format the current document"
            },
            None,  # Separator
            {
                'name': 'uppercase',
                'text': "Convert to &Uppercase",
                'shortcut': "Ctrl+Shift+U",
                'icon': "uppercase.png",
                'slot': lambda: self._change_case('upper'),
                'status_tip': "Convert selected text to uppercase"
            },
            {
                'name': 'lowercase',
                'text': "Convert to &Lowercase",
                'shortcut': "Ctrl+Shift+L",
                'icon': "lowercase.png",
                'slot': lambda: self._change_case('lower'),
                'status_tip': "Convert selected text to lowercase"
            }
        ]

        # Create and add actions
        self.advanced_edit_actions = {}
        for action_def in actions:
            if action_def is None:
                advanced_menu.addSeparator()
                continue

            action = self._create_action(action_def)
            self.advanced_edit_actions[action_def['name']] = action
            advanced_menu.addAction(action)

        return advanced_menu

    def _create_view_menu(self) -> QMenu:
        """
        Create View menu with all related actions

        Last modified: 2025-02-16 17:32:20
        Modified by: vcutrone

        Returns:
            QMenu: Configured View menu
        """
        view_menu = QMenu("&View", self)

        # Create view mode actions group
        view_mode_group = QActionGroup(self)
        view_mode_group.setExclusive(True)

        # Define view mode actions
        view_modes = [
            {
                'name': 'code_view',
                'text': "&Code View",
                'shortcut': "Ctrl+1",
                'icon': "code_view.png",
                'slot': self._show_code_view,
                'status_tip': "Switch to code view",
                'checkable': True,
                'checked': True
            },
            {
                'name': 'design_view',
                'text': "&Design View",
                'shortcut': "Ctrl+2",
                'icon': "design_view.png",
                'slot': self._show_design_view,
                'status_tip': "Switch to design view",
                'checkable': True
            },
            {
                'name': 'split_view',
                'text': "&Split View",
                'shortcut': "Ctrl+3",
                'icon': "split_view.png",
                'slot': self._show_split_view,
                'status_tip': "Switch to split view",
                'checkable': True
            }
        ]

        # Create and add view mode actions
        self.view_mode_actions = {}
        for action_def in view_modes:
            action = self._create_action(action_def)
            view_mode_group.addAction(action)
            self.view_mode_actions[action_def['name']] = action
            view_menu.addAction(action)

        view_menu.addSeparator()

        # Create panels submenu
        panels_menu = self._create_panels_menu()
        view_menu.addMenu(panels_menu)

        view_menu.addSeparator()

        # Define additional view actions
        actions = [
            {
                'name': 'zoom_in',
                'text': "Zoom &In",
                'shortcut': QKeySequence.StandardKey.ZoomIn,
                'icon': "zoom_in.png",
                'slot': self._zoom_in,
                'status_tip': "Increase zoom level"
            },
            {
                'name': 'zoom_out',
                'text': "Zoom &Out",
                'shortcut': QKeySequence.StandardKey.ZoomOut,
                'icon': "zoom_out.png",
                'slot': self._zoom_out,
                'status_tip': "Decrease zoom level"
            },
            {
                'name': 'zoom_reset',
                'text': "&Reset Zoom",
                'shortcut': "Ctrl+0",
                'icon': "zoom_reset.png",
                'slot': self._zoom_reset,
                'status_tip': "Reset zoom level to 100%"
            },
            None,  # Separator
            {
                'name': 'full_screen',
                'text': "&Full Screen",
                'shortcut': "F11",
                'icon': "full_screen.png",
                'slot': self._toggle_full_screen,
                'status_tip': "Toggle full screen mode",
                'checkable': True
            }
        ]

        # Create and add additional view actions
        self.view_actions = {}
        for action_def in actions:
            if action_def is None:
                view_menu.addSeparator()
                continue

            action = self._create_action(action_def)
            self.view_actions[action_def['name']] = action
            view_menu.addAction(action)

        return view_menu

    def _create_panels_menu(self) -> QMenu:
        """
        Create Panels submenu

        Last modified: 2025-02-16 17:32:20
        Modified by: vcutrone

        Returns:
            QMenu: Configured Panels submenu
        """
        panels_menu = QMenu("&Panels", self)

        # Define panel toggle actions
        panels = [
            {
                'name': 'file_browser',
                'text': "&File Browser",
                'shortcut': "Ctrl+B",
                'icon': "file_browser.png",
                'slot': self._toggle_file_browser,
                'status_tip': "Toggle file browser panel",
                'checkable': True,
                'checked': True
            },
            {
                'name': 'preview',
                'text': "&Preview",
                'shortcut': "Ctrl+P",
                'icon': "preview.png",
                'slot': self._toggle_preview,
                'status_tip': "Toggle preview panel",
                'checkable': True,
                'checked': True
            },
            {
                'name': 'git',
                'text': "&Git",
                'shortcut': "Ctrl+G",
                'icon': "git.png",
                'slot': self._toggle_git_panel,
                'status_tip': "Toggle Git panel",
                'checkable': True,
                'checked': True
            },
            {
                'name': 'outline',
                'text': "&Outline",
                'shortcut': "Ctrl+O",
                'icon': "outline.png",
                'slot': self._toggle_outline_panel,
                'status_tip': "Toggle document outline panel",
                'checkable': True,
                'checked': True
            }
        ]

        # Create and add panel toggle actions
        self.panel_actions = {}
        for action_def in panels:
            action = self._create_action(action_def)
            self.panel_actions[action_def['name']] = action
            panels_menu.addAction(action)

        return panels_menu

    def _create_tools_menu(self) -> QMenu:
        """
        Create Tools menu with all related actions

        Last modified: 2025-02-16 17:32:59
        Modified by: vcutrone

        Returns:
            QMenu: Configured Tools menu
        """
        tools_menu = QMenu("&Tools", self)

        # Define tools actions
        actions = [
            {
                'name': 'validate',
                'text': "&Validate HTML",
                'shortcut': "F7",
                'icon': "validate.png",
                'slot': self._validate_html,
                'status_tip': "Validate HTML code"
            },
            {
                'name': 'accessibility',
                'text': "Check &Accessibility",
                'shortcut': "F8",
                'icon': "accessibility.png",
                'slot': self._check_accessibility,
                'status_tip': "Check accessibility compliance"
            },
            None,  # Separator
            {
                'name': 'git_commit',
                'text': "&Git Commit...",
                'shortcut': "Ctrl+Alt+C",
                'icon': "git_commit.png",
                'slot': self._git_commit,
                'status_tip': "Commit changes to Git repository"
            },
            {
                'name': 'git_push',
                'text': "Git &Push...",
                'shortcut': "Ctrl+Alt+P",
                'icon': "git_push.png",
                'slot': self._git_push,
                'status_tip': "Push commits to remote repository"
            },
            {
                'name': 'git_pull',
                'text': "Git P&ull...",
                'shortcut': "Ctrl+Alt+L",
                'icon': "git_pull.png",
                'slot': self._git_pull,
                'status_tip': "Pull changes from remote repository"
            },
            None,  # Separator
            {
                'name': 'snippets',
                'text': "Manage &Snippets...",
                'shortcut': "Ctrl+Alt+S",
                'icon': "snippets.png",
                'slot': self._manage_snippets,
                'status_tip': "Manage code snippets"
            },
            {
                'name': 'emmet',
                'text': "&Emmet Settings...",
                'shortcut': "Ctrl+Alt+E",
                'icon': "emmet.png",
                'slot': self._emmet_settings,
                'status_tip': "Configure Emmet settings"
            }
        ]

        # Create and add actions
        self.tools_actions = {}
        for action_def in actions:
            if action_def is None:
                tools_menu.addSeparator()
                continue

            action = self._create_action(action_def)
            self.tools_actions[action_def['name']] = action
            tools_menu.addAction(action)

        return tools_menu

    def _create_action(self, definition: Dict[str, Any]) -> QAction:
        """
        Create a QAction from a definition dictionary

        Last modified: 2025-02-16 17:32:59
        Modified by: vcutrone

        Args:
            definition: Dictionary containing action properties

        Returns:
            QAction: Configured action
        """
        try:
            action = QAction(definition['text'], self)

            # Set shortcut if defined
            if 'shortcut' in definition:
                action.setShortcut(definition['shortcut'])

            # Set icon if defined
            if 'icon' in definition:
                icon_path = os.path.join("resources", "icons", definition['icon'])
                if os.path.exists(icon_path):
                    action.setIcon(QIcon(icon_path))

            # Set slot if defined
            if 'slot' in definition:
                action.triggered.connect(definition['slot'])

            # Set status tip if defined
            if 'status_tip' in definition:
                action.setStatusTip(definition['status_tip'])

            # Set checkable state if defined
            if 'checkable' in definition:
                action.setCheckable(definition['checkable'])

            # Set checked state if defined
            if 'checked' in definition:
                action.setChecked(definition['checked'])

            return action

        except Exception as e:
            logger.error(
                f"[{AppConfig.TIMESTAMP}] Failed to create action "
                f"'{definition.get('name', 'unknown')}': {str(e)}"
            )
            raise

    def _create_toolbars(self):
        """
        Create and configure application toolbars

        Last modified: 2025-02-16 17:33:42
        Modified by: vcutrone
        """
        try:
            # Create main toolbar
            self.main_toolbar = QToolBar("Main Toolbar")
            self.main_toolbar.setObjectName("MainToolBar")
            self.addToolBar(self.main_toolbar)

            # Add file operations
            for action_name in ['new', 'open', 'save', 'save_all']:
                if action_name in self.file_actions:
                    self.main_toolbar.addAction(self.file_actions[action_name])

            self.main_toolbar.addSeparator()

            # Add edit operations
            for action_name in ['undo', 'redo', 'cut', 'copy', 'paste']:
                if action_name in self.edit_actions:
                    self.main_toolbar.addAction(self.edit_actions[action_name])

            self.main_toolbar.addSeparator()

            # Add view operations
            for action_name in ['code_view', 'design_view', 'split_view']:
                if action_name in self.view_mode_actions:
                    self.main_toolbar.addAction(self.view_mode_actions[action_name])

            # Create HTML elements toolbar
            self._create_html_toolbar()

            # Create formatting toolbar
            self._create_formatting_toolbar()

            logger.debug(
                f"[{AppConfig.TIMESTAMP}] Toolbars created successfully"
            )

        except Exception as e:
            logger.error(
                f"[{AppConfig.TIMESTAMP}] Failed to create toolbars: {str(e)}"
            )
            raise

    def _create_html_toolbar(self):
        """
        Create toolbar for HTML elements

        Last modified: 2025-02-16 17:33:42
        Modified by: vcutrone
        """
        try:
            self.html_toolbar = QToolBar("HTML Elements")
            self.html_toolbar.setObjectName("HTMLToolBar")
            self.addToolBar(self.html_toolbar)

            # Define HTML elements with their templates
            html_elements = [
                ('div', 'Division Container', '<div>\n    ${cursor}\n</div>'),
                ('p', 'Paragraph', '<p>${cursor}</p>'),
                ('a', 'Link', '<a href="#">${cursor}</a>'),
                ('img', 'Image', '<img src="" alt="${cursor}">'),
                ('table', 'Table', '<table>\n    <tr>\n        <td>${cursor}</td>\n    </tr>\n</table>'),
                ('form', 'Form', '<form action="" method="post">\n    ${cursor}\n</form>'),
                ('input', 'Input Field', '<input type="text" name="" id="${cursor}">'),
                ('button', 'Button', '<button type="button">${cursor}</button>'),
                ('ul', 'Unordered List', '<ul>\n    <li>${cursor}</li>\n</ul>'),
                ('ol', 'Ordered List', '<ol>\n    <li>${cursor}</li>\n</ol>')
            ]

            # Create actions for HTML elements
            self.html_element_actions = {}
            for element, tooltip, template in html_elements:
                action = QAction(QIcon(f"resources/icons/html_{element}.png"),
                                 element.upper(), self)
                action.setToolTip(tooltip)
                action.setData(template)
                action.triggered.connect(
                    lambda checked, e=element: self._insert_html_element(e)
                )
                self.html_element_actions[element] = action
                self.html_toolbar.addAction(action)

            logger.debug(
                f"[{AppConfig.TIMESTAMP}] HTML toolbar created successfully"
            )

        except Exception as e:
            logger.error(
                f"[{AppConfig.TIMESTAMP}] Failed to create HTML toolbar: {str(e)}"
            )
            raise

    def _create_formatting_toolbar(self):
        """
        Create toolbar for text formatting

        Last modified: 2025-02-16 17:33:42
        Modified by: vcutrone
        """
        try:
            self.formatting_toolbar = QToolBar("Formatting")
            self.formatting_toolbar.setObjectName("FormattingToolBar")
            self.addToolBar(self.formatting_toolbar)

            # Add font family combo box
            self.font_family_combo = QComboBox()
            self.font_family_combo.addItems(QFontDatabase().families())
            self.font_family_combo.setCurrentText(
                self.managers['settings'].get_value('editor/font_family', 'Consolas')
            )
            self.font_family_combo.currentTextChanged.connect(self._change_font_family)
            self.formatting_toolbar.addWidget(self.font_family_combo)

            # Add font size combo box
            self.font_size_combo = QComboBox()
            self.font_size_combo.addItems([str(size) for size in range(8, 73, 2)])
            self.font_size_combo.setCurrentText(
                str(self.managers['settings'].get_value('editor/font_size', 12))
            )
            self.font_size_combo.currentTextChanged.connect(self._change_font_size)
            self.formatting_toolbar.addWidget(self.font_size_combo)

            self.formatting_toolbar.addSeparator()

            # Add text alignment actions
            alignments = [
                ('left', 'Align Left', Qt.AlignmentFlag.AlignLeft),
                ('center', 'Align Center', Qt.AlignmentFlag.AlignCenter),
                ('right', 'Align Right', Qt.AlignmentFlag.AlignRight),
                ('justify', 'Justify', Qt.AlignmentFlag.AlignJustify)
            ]

            alignment_group = QActionGroup(self)
            alignment_group.setExclusive(True)

            for name, tooltip, alignment in alignments:
                action = QAction(QIcon(f"resources/icons/align_{name}.png"),
                                 tooltip, self)
                action.setCheckable(True)
                action.setData(alignment)
                action.triggered.connect(
                    lambda checked, a=alignment: self._set_text_alignment(a)
                )
                alignment_group.addAction(action)
                self.formatting_toolbar.addAction(action)

            logger.debug(
                f"[{AppConfig.TIMESTAMP}] Formatting toolbar created successfully"
            )

        except Exception as e:
            logger.error(
                f"[{AppConfig.TIMESTAMP}] Failed to create formatting toolbar: {str(e)}"
            )
            raise


if __name__ == '__main__':
    try:
        # Create application instance
        app = QApplication(sys.argv)

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/cloudworks.log'),
                logging.StreamHandler()
            ]
        )

        # Create and show main window
        main_window = MainWindow()
        main_window.show()

        # Start event loop
        sys.exit(app.exec())

    except Exception as e:
        logging.critical(f"Application failed to start: {str(e)}")
        sys.exit(1)
