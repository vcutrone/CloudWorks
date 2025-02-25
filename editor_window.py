#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CloudWorks HTML Editor - Editor Window
Created on: 2025-02-08 13:27:56
Last Modified: 2025-02-16 15:15:23
Author: vcutrone
Version: 1.0.0

This module implements the main editor window functionality, providing features like:
- Advanced HTML editing with syntax highlighting
- Live preview with auto-refresh
- Git integration
- Code formatting and validation
- Accessibility checking
- Snippet management
- Multi-cursor support
- Search and replace functionality
- Auto-save and backup
"""

import os
import sys
import re
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Union, Tuple
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFrame, QToolBar, QTextEdit, QMenuBar, QMenu, QStatusBar,
    QFileDialog, QMessageBox, QDockWidget, QTreeView, QTabWidget,
    QInputDialog, QLineEdit, QProgressDialog, QLabel, QComboBox,
    QCheckBox, QPushButton, QFontComboBox, QSpinBox,
    QToolButton, QScrollArea, QProgressBar, QApplication, QDialog
)

from PyQt6.QtCore import (
    Qt, pyqtSignal, QDir, QTimer, QEvent, QSize, QPoint, QUrl, QFile,
    QTextStream, QByteArray, QSettings, QRect, QThread
)

from PyQt6.QtGui import (
    QAction, QIcon, QKeySequence, QFontDatabase, QTextCharFormat,
    QColor, QPalette, QTextCursor, QTextDocument, QTextBlockFormat,
    QSyntaxHighlighter, QFont, QFontMetrics, QActionGroup, QClipboard
)

# Try to import WebEngine components, but don't fail if not available
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage

    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    logging.warning("WebEngine components not available - some features will be disabled")

    # Import local modules
    from core.template_manager import TemplateManager
    from core.project_manager import ProjectManager
    from core.file_manager import FileManager
    from core.settings_manager import SettingsManager
    from core.html_parser import HTMLParser
    from core.css_manager import CSSManager
    from core.syntax_manager import HTMLHighlighter
    from utils.git_manager import GitManager
    from utils.snippet_manager import SnippetManager
    from utils.emmet_handler import EmmetHandler
    from utils.accessibility_checker import AccessibilityChecker

    # Constants
    DEFAULT_ENCODING = 'utf-8'
    DEFAULT_TAB_SIZE = 4
    CURRENT_TIMESTAMP = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    CURRENT_USER = "vcutrone"
    AUTO_SAVE_INTERVAL = 300000  # 5 minutes in milliseconds
    MAX_RECENT_FILES = 10
    DEFAULT_FONT_FAMILY = "Source Code Pro"
    DEFAULT_FONT_SIZE = 12

    # Create logs directory if it doesn't exist
    try:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # Setup logging configuration
        log_file = os.path.join(log_dir, f'editor_{datetime.now().strftime("%Y%m%d")}.log')

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

        logger = logging.getLogger(__name__)
        logger.info(f"Editor logging initialized at {CURRENT_TIMESTAMP}")

    except Exception as e:
        print(f"Failed to initialize logging: {str(e)}")
        # Fallback to basic logging
        logging.basicConfig(level=logging.WARNING)
        logger = logging.getLogger(__name__)


    class EditorWindow(QMainWindow):
        """
        Main editor window class implementing HTML editing functionality
        with advanced features like Git integration, live preview, and more.
        Last modified: 2025-02-16 15:16:23
        Modified by: vcutrone
        """

        # Custom signals
        documentModified = pyqtSignal(bool)
        gitStatusChanged = pyqtSignal(dict)
        previewUpdated = pyqtSignal()
        cursorPositionChanged = pyqtSignal(int, int)
        selectionChanged = pyqtSignal(bool)
        themeChanged = pyqtSignal(str)

        def __init__(self, parent=None):
            """Initialize the editor window with all required components"""
            super().__init__(parent)

            # Initialize logging for this instance
            self.logger = logging.getLogger(f"{__name__}.{id(self)}")
            self.logger.info(f"[{CURRENT_TIMESTAMP}] Initializing editor window")

            try:
                # Initialize instance variables
                self.current_file = None
                self.modified = False
                self.auto_save_enabled = True
                self.preview_enabled = True
                self.multi_cursors = []
                self.search_state = {}
                self.git_config = {}
                self.completion_settings = {}

                # Initialize managers
                self.initialize_managers()

                # Load configuration
                self.load_config()

                # Setup UI components
                self.setup_ui()
                self.setup_connections()
                self.setup_shortcuts()

                # Initialize timers
                self.setup_timers()

                # Create first empty tab
                self.new_file()

                self.logger.info(f"[{CURRENT_TIMESTAMP}] Editor window initialized successfully")

            except Exception as e:
                self.logger.error(f"[{CURRENT_TIMESTAMP}] Error initializing editor window: {str(e)}")
                QMessageBox.critical(self, "Initialization Error",
                                     f"Failed to initialize editor: {str(e)}")
                raise

        def initialize_managers(self):
            """Initialize all manager components"""
            try:
                self.settings_manager = SettingsManager()
                self.template_manager = TemplateManager()
                self.project_manager = ProjectManager()
                self.file_manager = FileManager()
                self.git_manager = GitManager()
                self.snippet_manager = SnippetManager()
                self.emmet_handler = EmmetHandler()
                self.html_parser = HTMLParser()
                self.css_manager = CSSManager()

                self.logger.info(f"[{CURRENT_TIMESTAMP}] Managers initialized successfully")

            except Exception as e:
                self.logger.error(f"[{CURRENT_TIMESTAMP}] Error initializing managers: {str(e)}")
                raise

        def load_config(self):
            """Load editor configuration from settings"""
            try:
                # Load editor settings
                settings = self.settings_manager.get_editor_settings()

                # Editor configuration
                self.editor_font = QFont(
                    settings.get('font_family', DEFAULT_FONT_FAMILY),
                    settings.get('font_size', DEFAULT_FONT_SIZE)
                )
                self.tab_size = settings.get('tab_size', DEFAULT_TAB_SIZE)
                self.use_spaces = settings.get('use_spaces', True)

                # Feature flags
                self.enable_auto_completion = settings.get('auto_completion', True)
                self.completion_trigger_len = settings.get('completion_trigger_length', 2)
                self.enable_auto_pairs = settings.get('auto_pairs', True)
                self.show_line_numbers = settings.get('show_line_numbers', True)
                self.highlight_current_line = settings.get('highlight_current_line', True)
                self.word_wrap = settings.get('word_wrap', False)

                # Auto-pairs configuration
                self.auto_pairs = {
                    '(': ')',
                    '[': ']',
                    '{': '}',
                    '"': '"',
                    "'": "'",
                    '<': '>'
                }

                self.logger.info(f"[{CURRENT_TIMESTAMP}] Configuration loaded successfully")

            except Exception as e:
                self.logger.error(f"[{CURRENT_TIMESTAMP}] Error loading configuration: {str(e)}")
                raise

        def current_editor(self) -> Optional[QTextEdit]:
            """Get the currently active editor widget"""
            try:
                current_tab = self.tab_widget.currentWidget()
                if isinstance(current_tab, QTextEdit):
                    return current_tab
                return None

            except Exception as e:
                self.logger.error(f"[{CURRENT_TIMESTAMP}] Error getting current editor: {str(e)}")
                return None

        def new_file(self) -> Optional[QTextEdit]:
            """Create a new file tab"""
            try:
                # Create new editor
                editor = QTextEdit()
                editor.setFont(self.editor_font)

                # Setup syntax highlighting
                highlighter = HTMLHighlighter(editor.document())

                # Configure editor
                self.configure_editor(editor)

                # Add to tab widget
                index = self.tab_widget.addTab(editor, "Untitled")
                self.tab_widget.setCurrentIndex(index)

                # Set focus
                editor.setFocus()

                self.logger.info(f"[{CURRENT_TIMESTAMP}] New file created successfully")

                return editor

            except Exception as e:
                self.logger.error(f"[{CURRENT_TIMESTAMP}] Error creating new file: {str(e)}")
                QMessageBox.critical(self, "Error", f"Could not create new file: {str(e)}")
                return None

        def configure_editor(self, editor: QTextEdit):
            """Configure editor settings and behavior"""
            try:
                # Set editor properties
                editor.setLineWrapMode(
                    QTextEdit.LineWrapMode.WidgetWidth if self.word_wrap
                    else QTextEdit.LineWrapMode.NoWrap
                )
                editor.setTabStopDistance(
                    self.tab_size * QFontMetrics(editor.font()).horizontalAdvance(' ')
                )

                # Enable line numbers if configured
                if self.show_line_numbers:
                    self.add_line_numbers(editor)

                # Configure auto-completion
                if self.enable_auto_completion:
                    self.setup_auto_completion(editor)

                # Set up custom context menu
                editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                editor.customContextMenuRequested.connect(
                    lambda pos: self.show_editor_context_menu(editor, pos)
                )

                # Connect editor signals
                editor.textChanged.connect(lambda: self.handle_text_changed(editor))
                editor.cursorPositionChanged.connect(
                    lambda: self.handle_cursor_position_changed(editor)
                )

                self.logger.info(f"[{CURRENT_TIMESTAMP}] Editor configured successfully")

            except Exception as e:
                self.logger.error(f"[{CURRENT_TIMESTAMP}] Error configuring editor: {str(e)}")
                raise

        def handle_content_changed(self) -> None:
            """Handle content changes in the editor"""
            try:
                if self.current_editor():
                    # Update modified state
                    self.is_modified = True

                    # Update status bar
                    self.update_status_bar()

                    # Trigger auto-save if enabled
                    if self.auto_save_enabled:
                        self.auto_save_timer.start()

            except Exception as e:
                self.logger.error(
                    f"[{CURRENT_TIMESTAMP}] Error handling content change: {str(e)}"
                )

        def setup_ui(self):
            """Initialize and setup all UI components"""
            try:
                # Set window properties
                self.setWindowTitle("CloudWorks HTML Editor")
                self.setMinimumSize(1024, 768)

                # Create central widget and main layout
                self.central_widget = QWidget()
                self.setCentralWidget(self.central_widget)
                self.main_layout = QVBoxLayout(self.central_widget)
                self.main_layout.setContentsMargins(0, 0, 0, 0)

                # Create main splitter
                self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
                self.main_layout.addWidget(self.main_splitter)

                # Setup UI components
                self.setup_editor_section()
                self.setup_preview_section()
                self.setup_toolbars()
                self.setup_menus()
                self.setup_status_bar()
                self.setup_dock_widgets()

                # Apply current theme
                self.apply_theme(self.settings_manager.get_value("theme", "light"))

                self.logger.info(f"[2025-02-16 15:17:26] UI setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:17:26] Error setting up UI: {str(e)}")
                raise

        def handle_paste_event(self, event: QEvent) -> None:
            """
            Handle paste events from clipboard
            
            Args:
                event (QEvent): The paste event from the system clipboard
            """
            try:
                # Initial logging of paste attempt
                self.logger.debug(f"[2025-02-16 15:17:26] Paste event triggered by vcutrone")

                # Validate event type
                if event.type() != QEvent.Type.Paste:
                    self.logger.debug(f"[2025-02-16 15:17:26] Invalid event type: {event.type()}")
                    event.ignore()
                    return

                # Get clipboard and validate editor
                clipboard = QApplication.clipboard()
                if not self.current_editor():
                    self.logger.error(f"[2025-02-16 15:17:26] No active editor for paste operation")
                    event.ignore()
                    return

                mime_data = clipboard.mimeData()
                cursor = self.current_editor().textCursor()

                # Start an undo operation group
                cursor.beginEditBlock()

                try:
                    if mime_data.hasText():
                        text = mime_data.text()

                        # Handle HTML content with fallback
                        if mime_data.hasHtml():
                            try:
                                html = mime_data.html()
                                cleaned_html = self.sanitize_html(html)
                                if cleaned_html:
                                    text = cleaned_html
                                    self.logger.debug(
                                        f"[2025-02-16 15:17:26] HTML content processed "
                                        f"successfully by vcutrone"
                                    )
                            except Exception as html_error:
                                self.logger.warning(
                                    f"[2025-02-16 15:17:26] HTML processing failed, "
                                    f"falling back to plain text: {str(html_error)}"
                                )

                        # Store current position
                        initial_position = cursor.position()

                        # Insert the text
                        cursor.insertText(text)

                        # Update cursor position
                        self.current_editor().setTextCursor(cursor)

                        # Apply syntax highlighting if available
                        if hasattr(self, 'syntax_highlighter') and self.syntax_highlighter:
                            try:
                                self.syntax_highlighter.rehighlight()
                                self.logger.debug(
                                    f"[2025-02-16 15:17:26] Syntax highlighting "
                                    f"refreshed by vcutrone"
                                )
                            except Exception as highlight_error:
                                self.logger.warning(
                                    f"[2025-02-16 15:17:26] Syntax highlighting "
                                    f"failed: {str(highlight_error)}"
                                )

                        # Accept the event
                        event.accept()

                        # Trigger content change handlers
                        self.handle_content_changed()

                        # Log successful paste
                        self.logger.debug(
                            f"[2025-02-16 15:17:26] Paste operation completed by "
                            f"vcutrone - Characters: {len(text)}, "
                            f"Position: {initial_position}"
                        )

                    else:
                        self.logger.warning(
                            f"[2025-02-16 15:17:26] No text content available "
                            f"in clipboard for vcutrone"
                        )
                        event.ignore()

                finally:
                    # End the undo operation group
                    cursor.endEditBlock()

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:17:26] Critical error in paste event "
                    f"handler for vcutrone: {str(e)}"
                )
                # Ensure the event is ignored on error
                event.ignore()

                # Try to restore editor state if possible
                try:
                    if self.current_editor():
                        self.current_editor().undo()
                except:
                    pass  # Silent failure on recovery attempt

        def sanitize_html(self, html: str) -> str:
            """
            Sanitize HTML content for safe pasting
            
            Args:
                html (str): Raw HTML content from clipboard
                
            Returns:
                str: Sanitized HTML content or empty string if invalid
            """
            try:
                # Basic sanitization
                cleaned = html.replace("<script", "&lt;script") \
                    .replace("javascript:", "") \
                    .replace("on", "data-on")  # Disable event handlers

                # Remove potentially harmful tags
                harmful_tags = ['script', 'style', 'iframe', 'object', 'embed']
                for tag in harmful_tags:
                    cleaned = re.sub(
                        f'<{tag}.*?</{tag}>',
                        '',
                        cleaned,
                        flags=re.IGNORECASE | re.DOTALL
                    )

                return cleaned

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:17:26] HTML sanitization failed for "
                    f"vcutrone: {str(e)}"
                )
                return ""

        def setup_connections(self):
            """Setup all signal-slot connections"""
            try:
                # Editor connections
                editor = self.current_editor()
                if editor:
                    editor.textChanged.connect(self.handle_text_changed)
                    editor.cursorPositionChanged.connect(self.handle_cursor_position_changed)
                    editor.selectionChanged.connect(self.handle_selection_changed)
                    editor.modificationChanged.connect(self.handle_modification_changed)

                # Tab widget connections
                self.tab_widget.currentChanged.connect(self.handle_tab_changed)
                self.tab_widget.tabCloseRequested.connect(self.close_tab)

                # Git manager connections
                self.git_manager.statusChanged.connect(self.update_git_status)
                self.git_manager.operationComplete.connect(self.handle_git_operation_complete)
                self.git_manager.errorOccurred.connect(self.handle_git_error)

                # Preview connections
                if hasattr(self, 'auto_refresh'):
                    self.auto_refresh.stateChanged.connect(self.toggle_auto_refresh)
                if hasattr(self, 'preview_view'):
                    self.preview_view.loadFinished.connect(self.handle_preview_load_finished)

                # Project manager connections
                self.project_manager.projectOpened.connect(self.handle_project_opened)
                self.project_manager.projectClosed.connect(self.handle_project_closed)
                self.project_manager.fileAdded.connect(self.handle_project_file_added)
                self.project_manager.fileRemoved.connect(self.handle_project_file_removed)

                self.logger.info(f"[2025-02-16 15:17:26] Signal-slot connections setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:17:26] Error setting up connections: {str(e)}")
                raise

        def setup_toolbars(self):
            """Setup main toolbar and additional toolbars"""
            try:
                # Create main toolbar
                self.main_toolbar = QToolBar()
                self.addToolBar(self.main_toolbar)

                # File operations
                self.main_toolbar.addAction(QIcon(":/icons/new.png"), "New File", self.new_file)
                self.main_toolbar.addAction(QIcon(":/icons/open.png"), "Open File", self.open_file)
                self.main_toolbar.addAction(QIcon(":/icons/save.png"), "Save File", self.save_file)
                self.main_toolbar.addSeparator()

                # Edit operations
                self.main_toolbar.addAction(QIcon(":/icons/undo.png"), "Undo", self.undo)
                self.main_toolbar.addAction(QIcon(":/icons/redo.png"), "Redo", self.redo)
                self.main_toolbar.addSeparator()

                # Add formatting toolbar
                self.setup_formatting_toolbar()

                # Add HTML toolbar
                self.setup_html_toolbar()

                self.logger.info(f"[2025-02-16 15:18:21] Toolbars setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:18:21] Error setting up toolbars: {str(e)}")
                raise

        def setup_formatting_toolbar(self):
            """Setup the formatting toolbar with text formatting options"""
            try:
                self.formatting_toolbar = QToolBar()
                self.addToolBar(self.formatting_toolbar)

                # Font family selector
                self.font_family = QFontComboBox()
                self.font_family.setCurrentFont(QFont(DEFAULT_FONT_FAMILY))
                self.font_family.currentFontChanged.connect(self.change_font)
                self.formatting_toolbar.addWidget(self.font_family)

                # Font size selector
                self.font_size = QSpinBox()
                self.font_size.setRange(8, 72)
                self.font_size.setValue(DEFAULT_FONT_SIZE)
                self.font_size.valueChanged.connect(self.change_font_size)
                self.formatting_toolbar.addWidget(self.font_size)

                self.formatting_toolbar.addSeparator()

                # Text formatting actions
                self.add_formatting_actions()

                self.logger.info(f"[2025-02-16 15:18:21] Formatting toolbar setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:18:21] Error setting up formatting toolbar: {str(e)}")
                raise

        def add_formatting_actions(self):
            """Add text formatting action buttons"""
            try:
                # Bold
                bold_action = QAction(QIcon(":/icons/bold.png"), "Bold", self)
                bold_action.setShortcut("Ctrl+B")
                bold_action.triggered.connect(lambda: self.format_text("bold"))
                self.formatting_toolbar.addAction(bold_action)

                # Italic
                italic_action = QAction(QIcon(":/icons/italic.png"), "Italic", self)
                italic_action.setShortcut("Ctrl+I")
                italic_action.triggered.connect(lambda: self.format_text("italic"))
                self.formatting_toolbar.addAction(italic_action)

                # Underline
                underline_action = QAction(QIcon(":/icons/underline.png"), "Underline", self)
                underline_action.setShortcut("Ctrl+U")
                underline_action.triggered.connect(lambda: self.format_text("underline"))
                self.formatting_toolbar.addAction(underline_action)

                self.logger.debug(f"[2025-02-16 15:18:21] Formatting actions added by {CURRENT_USER}")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:18:21] Error adding formatting actions: {str(e)}")
                raise

        def setup_html_toolbar(self):
            """Setup the HTML-specific toolbar with common HTML elements"""
            try:
                self.html_toolbar = QToolBar()
                self.addToolBar(self.html_toolbar)

                # HTML structure elements
                self.add_html_button("div", "<div></div>", "Division")
                self.add_html_button("span", "<span></span>", "Span")
                self.add_html_button("p", "<p></p>", "Paragraph")
                self.add_html_button("br", "<br>", "Line Break")
                self.html_toolbar.addSeparator()

                # Add headings dropdown
                self.add_headings_menu()

                # Add lists dropdown
                self.add_lists_menu()

                # Add table tools
                self.add_table_tools()

                self.logger.info(f"[2025-02-16 15:18:21] HTML toolbar setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:18:21] Error setting up HTML toolbar: {str(e)}")
                raise

        def add_headings_menu(self):
            """Add headings dropdown menu"""
            try:
                headings_button = QToolButton()
                headings_button.setText("Headings")
                headings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

                headings_menu = QMenu(headings_button)
                for i in range(1, 7):
                    action = headings_menu.addAction(f"H{i}")
                    action.triggered.connect(
                        lambda checked, h=i: self.insert_html(f"<h{h}></h{h}>")
                    )

                headings_button.setMenu(headings_menu)
                self.html_toolbar.addWidget(headings_button)

                self.logger.debug(f"[2025-02-16 15:18:21] Headings menu added by {CURRENT_USER}")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:18:21] Error adding headings menu: {str(e)}")
                raise

        def add_lists_menu(self):
            """Add lists dropdown menu"""
            try:
                lists_button = QToolButton()
                lists_button.setText("Lists")
                lists_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

                lists_menu = QMenu(lists_button)

                # Unordered list
                lists_menu.addAction("Unordered List").triggered.connect(
                    lambda: self.insert_html("<ul>\n  <li></li>\n</ul>")
                )

                # Ordered list
                lists_menu.addAction("Ordered List").triggered.connect(
                    lambda: self.insert_html("<ol>\n  <li></li>\n</ol>")
                )

                # List item
                lists_menu.addAction("List Item").triggered.connect(
                    lambda: self.insert_html("<li></li>")
                )

                lists_button.setMenu(lists_menu)
                self.html_toolbar.addWidget(lists_button)

                self.logger.debug(f"[2025-02-16 15:18:21] Lists menu added by {CURRENT_USER}")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:18:21] Error adding lists menu: {str(e)}")
                raise

        def setup_status_bar(self):
            """Setup the status bar with additional information panels"""
            try:
                self.status_bar = QStatusBar()
                self.setStatusBar(self.status_bar)

                # Cursor position label
                self.cursor_position_label = QLabel("Line: 1, Column: 1")
                self.status_bar.addPermanentWidget(self.cursor_position_label)

                # Document statistics
                self.stats_label = QLabel("Characters: 0 | Words: 0")
                self.status_bar.addPermanentWidget(self.stats_label)

                # Encoding label
                self.encoding_label = QLabel(f"Encoding: {DEFAULT_ENCODING}")
                self.status_bar.addPermanentWidget(self.encoding_label)

                # Git branch label
                self.git_branch_label = QLabel()
                self.status_bar.addPermanentWidget(self.git_branch_label)

                # File modification indicator
                self.modification_indicator = QLabel()
                self.status_bar.addPermanentWidget(self.modification_indicator)

                # Update status bar
                self.update_status_bar()

                self.logger.info(f"[2025-02-16 15:18:21] Status bar setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:18:21] Error setting up status bar: {str(e)}")
                raise

        def setup_timers(self):
            """Setup and initialize all timers"""
            try:
                # Auto-save timer
                self.auto_save_timer = QTimer(self)
                self.auto_save_timer.timeout.connect(self.auto_save)
                if self.auto_save_enabled:
                    self.auto_save_timer.start(AUTO_SAVE_INTERVAL)

                # Preview refresh timer
                self.preview_timer = QTimer(self)
                self.preview_timer.timeout.connect(self.refresh_preview)
                if self.preview_enabled:
                    self.preview_timer.start(1000)  # 1-second refresh interval

                # Git status update timer
                self.git_timer = QTimer(self)
                self.git_timer.timeout.connect(self.update_git_status)
                self.git_timer.start(5000)  # 5-second update interval

                # Statistics update timer
                self.stats_timer = QTimer(self)
                self.stats_timer.timeout.connect(self.update_statistics)
                self.stats_timer.start(2000)  # 2-second update interval

                self.logger.info(f"[2025-02-16 15:19:14] Timers setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:19:14] Error setting up timers: {str(e)}")
                raise

        def add_line_numbers(self, editor: QTextEdit):
            """Add line numbers widget to editor"""
            try:
                line_numbers = QWidget(editor)
                line_numbers.setFixedWidth(50)
                layout = QVBoxLayout(line_numbers)
                layout.setSpacing(0)
                layout.setContentsMargins(0, 0, 0, 0)

                # Create label for line numbers
                numbers_label = QLabel(line_numbers)
                numbers_label.setAlignment(Qt.AlignmentFlag.AlignRight)
                layout.addWidget(numbers_label)

                # Update line numbers when document changes
                def update_line_numbers():
                    block = editor.document().begin()
                    numbers = []
                    while block.isValid():
                        numbers.append(str(block.blockNumber() + 1))
                        block = block.next()
                    numbers_label.setText('\n'.join(numbers))

                editor.document().blockCountChanged.connect(update_line_numbers)
                update_line_numbers()

                self.logger.info(f"[2025-02-16 15:19:14] Line numbers added to editor")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:19:14] Error adding line numbers: {str(e)}")
                raise

        def setup_auto_completion(self, editor: QTextEdit):
            """Configure auto-completion for HTML and CSS"""
            try:
                # Load completion data
                self.html_completions = self.load_completions("html")
                self.css_completions = self.load_completions("css")

                # Create completion popup
                self.completion_popup = QMenu(editor)
                self.completion_popup.setFixedWidth(300)

                # Connect text changed signal for completion
                editor.textChanged.connect(lambda: self.handle_completion(editor))

                # Setup completion timer for performance
                self.completion_timer = QTimer(self)
                self.completion_timer.setSingleShot(True)
                self.completion_timer.timeout.connect(lambda: self.show_completions(editor))

                self.logger.info(f"[2025-02-16 15:19:14] Auto-completion setup completed")

            except Exception as e:
                self.logger.error(f"[2025-02-16 15:19:14] Error setting up auto-completion: {str(e)}")
                raise

        def load_completions(self, completion_type: str) -> Dict:
            """
            Load completion data from JSON files
            
            Args:
                completion_type (str): Type of completions to load ('html' or 'css')
                
            Returns:
                Dict: Loaded completion data or empty dict if loading fails
            """
            try:
                completion_file = f"resources/completions/{completion_type}.json"
                if not os.path.exists(completion_file):
                    self.logger.warning(
                        f"[2025-02-16 15:19:14] Completion file not found: {completion_file}"
                    )
                    return {}

                with open(completion_file, 'r', encoding='utf-8') as f:
                    completions = json.load(f)

                self.logger.info(
                    f"[2025-02-16 15:19:14] Loaded {completion_type} completions"
                )
                return completions

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:19:14] Error loading completions: {str(e)}"
                )
                return {}

        def handle_completion(self, editor: QTextEdit):
            """Handle text changes for auto-completion"""
            try:
                if not self.enable_auto_completion:
                    return

                # Reset completion timer
                self.completion_timer.stop()

                # Get current word
                cursor = editor.textCursor()
                current_word = self.get_current_word(cursor)

                if len(current_word) >= self.completion_trigger_len:
                    self.completion_timer.start(300)  # 300ms delay

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:19:14] Error handling completion: {str(e)}"
                )

        def show_completions(self, editor: QTextEdit):
            """Show completion popup with suggestions"""
            try:
                cursor = editor.textCursor()
                current_word = self.get_current_word(cursor)

                if len(current_word) < self.completion_trigger_len:
                    return

                # Get completion suggestions
                suggestions = self.get_completion_suggestions(current_word)

                if not suggestions:
                    return

                # Clear and populate completion popup
                self.completion_popup.clear()
                for suggestion in suggestions:
                    action = self.completion_popup.addAction(suggestion['label'])
                    action.triggered.connect(
                        lambda _, s=suggestion: self.insert_completion(editor, s)
                    )

                # Show popup at cursor position
                cursor_rect = editor.cursorRect(cursor)
                global_pos = editor.mapToGlobal(cursor_rect.bottomLeft())
                self.completion_popup.popup(global_pos)

                self.logger.debug(
                    f"[2025-02-16 15:19:14] Showing completion popup for '{current_word}'"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:19:14] Error showing completions: {str(e)}"
                )

        def get_current_word(self, cursor: QTextCursor) -> str:
            """
            Get the current word under the cursor
            
            Args:
                cursor (QTextCursor): The current text cursor
                
            Returns:
                str: The current word or empty string if none found
            """
            try:
                cursor.select(QTextCursor.SelectionType.WordUnderCursor)
                return cursor.selectedText()
            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:19:14] Error getting current word: {str(e)}"
                )
                return ""

        def get_completion_suggestions(self, word: str) -> List[Dict]:
            """
            Get completion suggestions for the current word
            
            Args:
                word (str): The word to get suggestions for
                
            Returns:
                List[Dict]: List of suggestion dictionaries
            """
            try:
                suggestions = []

                # Check HTML completions
                html_matches = [
                    {'label': tag, 'text': f"<{tag}></{tag}>"}
                    for tag in self.html_completions
                    if tag.startswith(word.lower())
                ]
                suggestions.extend(html_matches)

                # Check CSS completions
                css_matches = [
                    {'label': prop, 'text': f"{prop}: "}
                    for prop in self.css_completions
                    if prop.startswith(word.lower())
                ]
                suggestions.extend(css_matches)

                return suggestions[:10]  # Limit to 10 suggestions

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:19:14] Error getting completion suggestions: {str(e)}"
                )
                return []

        def update_status_bar(self):
            """Update all status bar widgets with current information"""
            try:
                editor = self.current_editor()
                if not editor:
                    return

                # Update cursor position
                cursor = editor.textCursor()
                line = cursor.blockNumber() + 1
                column = cursor.columnNumber() + 1
                self.cursor_position_label.setText(f"Line: {line}, Column: {column}")

                # Update document statistics
                text = editor.toPlainText()
                char_count = len(text)
                word_count = len(text.split())
                self.stats_label.setText(f"Characters: {char_count} | Words: {word_count}")

                # Update Git status if available
                if self.git_manager.is_git_repo():
                    branch = self.git_manager.current_branch()
                    self.git_branch_label.setText(f"Git: {branch}")
                else:
                    self.git_branch_label.clear()

                # Update modification indicator
                if self.is_modified:
                    self.modification_indicator.setText("Modified")
                else:
                    self.modification_indicator.clear()

                self.logger.debug(f"[2025-02-16 15:19:14] Status bar updated")

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:19:14] Error updating status bar: {str(e)}"
                )

        def get_current_word(self, cursor: QTextCursor) -> str:
            """
            Get the current word under cursor
            
            Args:
                cursor (QTextCursor): The current text cursor position
                
            Returns:
                str: The current word or empty string if none found
            """
            try:
                cursor.select(QTextCursor.SelectionType.WordUnderCursor)
                return cursor.selectedText()

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:22:55] Error getting current word: {str(e)}"
                )
                return ""

        def get_completion_suggestions(self, word: str) -> List[Dict]:
            """
            Get completion suggestions based on current word
            
            Args:
                word (str): The current word to get suggestions for
                
            Returns:
                List[Dict]: List of suggestion dictionaries with labels and snippets
            """
            try:
                suggestions = []

                # Check HTML completions
                for tag, data in self.html_completions.items():
                    if tag.startswith(word.lower()):
                        suggestions.append({
                            'label': tag,
                            'detail': data.get('description', ''),
                            'snippet': data.get('snippet', f'<{tag}></{tag}>')
                        })

                # Check CSS completions if in style tag or CSS file
                if self.is_css_context():
                    for prop, data in self.css_completions.items():
                        if prop.startswith(word.lower()):
                            suggestions.append({
                                'label': prop,
                                'detail': data.get('description', ''),
                                'snippet': f'{prop}: '
                            })

                return sorted(suggestions, key=lambda x: x['label'])

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:22:55] Error getting completion suggestions: {str(e)}"
                )
                return []

        def insert_completion(self, editor: QTextEdit, suggestion: Dict):
            """
            Insert the selected completion
            
            Args:
                editor (QTextEdit): The current editor instance
                suggestion (Dict): The suggestion to insert
            """
            try:
                cursor = editor.textCursor()

                # Remove current word
                cursor.movePosition(
                    QTextCursor.MoveOperation.StartOfWord,
                    QTextCursor.MoveMode.MoveAnchor
                )
                cursor.movePosition(
                    QTextCursor.MoveOperation.EndOfWord,
                    QTextCursor.MoveMode.KeepAnchor
                )

                # Insert suggestion
                cursor.insertText(suggestion['snippet'])

                # Move cursor inside tags if HTML
                if '<' in suggestion['snippet'] and '>' in suggestion['snippet']:
                    pos = cursor.position() - suggestion['snippet'].find('</') - 2
                    cursor.setPosition(pos)

                editor.setTextCursor(cursor)
                editor.setFocus()

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:22:55] Error inserting completion: {str(e)}"
                )

        def is_css_context(self) -> bool:
            """
            Determine if cursor is in CSS context
            
            Returns:
                bool: True if cursor is in CSS context, False otherwise
            """
            try:
                editor = self.current_editor()
                if not editor:
                    return False

                cursor = editor.textCursor()
                block_text = cursor.block().text()

                # Check if in style tag
                if '<style' in block_text or '</style>' in block_text:
                    return True

                # Check if CSS file
                current_file = self.get_current_file()
                return current_file and current_file.endswith('.css')

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:22:55] Error checking CSS context: {str(e)}"
                )
                return False

        def apply_preview_device_settings(self):
            """Apply device-specific settings to preview"""
            try:
                device = self.device_selector.currentText()

                # Define device dimensions
                dimensions = {
                    "Desktop": (1920, 1080),
                    "Tablet": (768, 1024),
                    "Mobile": (375, 667)
                }

                width, height = dimensions.get(device, (1920, 1080))

                # Apply device dimensions to preview
                self.preview_view.setFixedSize(width, height)
                self.preview_view.page().setViewportSize(QSize(width, height))

                # Apply device-specific user agent if needed
                if device != "Desktop":
                    user_agent = self.get_device_user_agent(device)
                    self.preview_view.page().profile().setHttpUserAgent(user_agent)

                self.logger.info(
                    f"[2025-02-16 15:22:55] Applied {device} preview settings"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:22:55] Error applying preview device settings: {str(e)}"
                )

        def get_device_user_agent(self, device: str) -> str:
            """
            Get appropriate user agent string for device
            
            Args:
                device (str): Device type ('Mobile' or 'Tablet')
                
            Returns:
                str: User agent string for the device
            """
            try:
                user_agents = {
                    "Mobile": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
                              "Mobile/15E148 Safari/604.1",
                    "Tablet": "Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
                              "Mobile/15E148 Safari/604.1"
                }

                return user_agents.get(device, "")

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:23:44] Error getting device user agent: {str(e)}"
                )
                return ""

        def handle_cursor_position_changed(self, editor: QTextEdit = None):
            """
            Update cursor position and handle related features
            
            Args:
                editor (QTextEdit, optional): The editor instance. If None, uses current editor.
            """
            try:
                if editor is None:
                    editor = self.current_editor()
                if not editor:
                    return

                cursor = editor.textCursor()
                line = cursor.blockNumber() + 1
                column = cursor.columnNumber() + 1

                # Update status bar
                self.cursor_position_label.setText(f"Line: {line}, Column: {column}")

                # Highlight current line if enabled
                if self.highlight_current_line:
                    self.highlight_current_line_in_editor(editor)

                # Check HTML tag matching
                self.highlight_matching_tags(editor)

                # Update context-sensitive tools
                self.update_context_tools(editor)

                self.logger.debug(
                    f"[2025-02-16 15:23:44] Cursor position changed: "
                    f"Line {line}, Column {column}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:23:44] Error handling cursor position change: {str(e)}"
                )

        def highlight_current_line_in_editor(self, editor: QTextEdit):
            """
            Highlight the current line in the editor
            
            Args:
                editor (QTextEdit): The editor instance to highlight the current line in
            """
            try:
                selection = QTextEdit.ExtraSelection()
                selection.format.setBackground(QColor("#f0f0f0"))
                selection.format.setProperty(
                    QTextFormat.Property.FullWidthSelection,
                    True
                )
                selection.cursor = editor.textCursor()
                selection.cursor.clearSelection()

                editor.setExtraSelections([selection])

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:23:44] Error highlighting current line: {str(e)}"
                )

        def highlight_matching_tags(self, editor: QTextEdit):
            """
            Highlight matching HTML tags
            
            Args:
                editor (QTextEdit): The editor instance to highlight tags in
            """
            try:
                cursor = editor.textCursor()
                document = editor.document()
                text = document.toPlainText()

                # Find tag under cursor
                tag_regex = r'<[^>]+>'
                matches = list(re.finditer(tag_regex, text))

                current_pos = cursor.position()
                current_tag = None
                matching_tag = None

                # Find current tag
                for match in matches:
                    if match.start() <= current_pos <= match.end():
                        current_tag = match
                        break

                if current_tag:
                    tag_content = current_tag.group()

                    # Find matching tag
                    if tag_content.startswith('</'):
                        # Looking for opening tag
                        tag_name = tag_content[2:-1]
                        matching_tag = self.find_opening_tag(
                            matches,
                            tag_name,
                            current_tag.start()
                        )
                    elif not tag_content.endswith('/>'):
                        # Looking for closing tag
                        tag_name = tag_content[1:].split()[0].rstrip('>')
                        matching_tag = self.find_closing_tag(
                            matches,
                            tag_name,
                            current_tag.end()
                        )

                # Highlight matched tags
                if current_tag and matching_tag:
                    self.highlight_tag_pair(editor, current_tag, matching_tag)

                self.logger.debug(f"[2025-02-16 15:23:44] Highlighted matching tags")

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:23:44] Error highlighting matching tags: {str(e)}"
                )

        def find_opening_tag(
                self,
                matches: List[re.Match],
                tag_name: str,
                current_pos: int
        ) -> Optional[re.Match]:
            """
            Find matching opening tag
            
            Args:
                matches (List[re.Match]): List of all tag matches in the document
                tag_name (str): Name of the tag to find
                current_pos (int): Current cursor position
                
            Returns:
                Optional[re.Match]: Matching opening tag or None if not found
            """
            try:
                stack = []
                for match in reversed(matches):
                    if match.end() >= current_pos:
                        continue

                    tag_content = match.group()
                    if tag_content.startswith('</') and tag_content[2:-1] == tag_name:
                        stack.append(match)
                    elif tag_content.startswith(f'<{tag_name}') and not tag_content.endswith('/>'):
                        if stack:
                            stack.pop()
                        else:
                            return match

                return None

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:23:44] Error finding opening tag: {str(e)}"
                )
                return None

        def find_closing_tag(
                self,
                matches: List[re.Match],
                tag_name: str,
                current_pos: int
        ) -> Optional[re.Match]:
            """
            Find matching closing tag
            
            Args:
                matches (List[re.Match]): List of all tag matches in the document
                tag_name (str): Name of the tag to find
                current_pos (int): Current cursor position
                
            Returns:
                Optional[re.Match]: Matching closing tag or None if not found
            """
            try:
                stack = []
                for match in matches:
                    if match.start() <= current_pos:
                        continue

                    tag_content = match.group()
                    if tag_content.startswith(f'<{tag_name}') and not tag_content.endswith('/>'):
                        stack.append(match)
                    elif tag_content == f'</{tag_name}>':
                        if stack:
                            stack.pop()
                        else:
                            return match

                return None

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:23:44] Error finding closing tag: {str(e)}"
                )
                return None

        def highlight_tag_pair(self, editor: QTextEdit, tag1: re.Match, tag2: re.Match):
            """
            Highlight a pair of matching tags
            
            Args:
                editor (QTextEdit): The editor instance
                tag1 (re.Match): First tag match
                tag2 (re.Match): Second tag match
            """
            try:
                selections = []

                # Highlight format
                format = QTextCharFormat()
                format.setBackground(QColor("#e6f3ff"))
                format.setForeground(QColor("#0066cc"))

                # Create selections for both tags
                for tag in (tag1, tag2):
                    selection = QTextEdit.ExtraSelection()
                    selection.format = format

                    cursor = editor.textCursor()
                    cursor.setPosition(tag.start())
                    cursor.setPosition(tag.end(), QTextCursor.MoveMode.KeepAnchor)

                    selection.cursor = cursor
                    selections.append(selection)

                # Apply selections
                editor.setExtraSelections(selections)

                self.logger.debug(f"[2025-02-16 15:24:34] Tag pair highlighted by {CURRENT_USER}")

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:24:34] Error highlighting tag pair: {str(e)}"
                )

        def update_context_tools(self, editor: QTextEdit):
            """
            Update context-sensitive tools based on cursor position
            
            Args:
                editor (QTextEdit): The editor instance
            """
            try:
                cursor = editor.textCursor()
                current_block_text = cursor.block().text()

                # Update HTML tag context
                tag_context = self.get_current_tag_context(
                    current_block_text,
                    cursor.columnNumber()
                )
                if tag_context:
                    self.update_tag_tools(tag_context)

                # Update CSS context
                if self.is_css_context():
                    self.update_css_tools()

                # Update accessibility checker
                self.check_accessibility_at_cursor()

                self.logger.debug(f"[2025-02-16 15:24:34] Context tools updated by {CURRENT_USER}")

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:24:34] Error updating context tools: {str(e)}"
                )

        def get_current_tag_context(self, text: str, position: int) -> Optional[Dict]:
            """
            Get context information about the current HTML tag
            
            Args:
                text (str): The text to analyze
                position (int): The cursor position in the text
                
            Returns:
                Optional[Dict]: Tag context information or None if not in a tag
            """
            try:
                tag_regex = r'<[^>]+>'
                matches = list(re.finditer(tag_regex, text))

                for match in matches:
                    if match.start() <= position <= match.end():
                        tag_content = match.group()
                        tag_name = re.match(r'</?([a-zA-Z0-9-]+)', tag_content)

                        if tag_name:
                            return {
                                'name': tag_name.group(1),
                                'opening': not tag_content.startswith('</'),
                                'self_closing': tag_content.endswith('/>'),
                                'attributes': self.parse_tag_attributes(tag_content)
                            }

                return None

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:24:34] Error getting tag context: {str(e)}"
                )
                return None

        def parse_tag_attributes(self, tag_content: str) -> Dict[str, str]:
            """
            Parse attributes from an HTML tag
            
            Args:
                tag_content (str): The content of the HTML tag
                
            Returns:
                Dict[str, str]: Dictionary of attribute names and values
            """
            try:
                attributes = {}
                attr_pattern = r'(\w+)(?:=["\']([^"\']*)["\'])?'

                # Remove tag brackets and tag name
                content = re.sub(r'^<\/?[\w-]+\s*', '', tag_content.rstrip('>'))

                for match in re.finditer(attr_pattern, content):
                    name = match.group(1)
                    value = match.group(2) if match.group(2) is not None else ''
                    attributes[name] = value

                return attributes

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:24:34] Error parsing tag attributes: {str(e)}"
                )
                return {}

        def check_accessibility_at_cursor(self):
            """Check accessibility issues at current cursor position"""
            try:
                editor = self.current_editor()
                if not editor:
                    return

                cursor = editor.textCursor()
                block_text = cursor.block().text()

                # Clear previous accessibility highlights
                self.clear_accessibility_highlights()

                # Check for common accessibility issues
                self.check_heading_structure(block_text)
                self.check_color_contrast()
                self.check_semantic_structure(block_text)
                self.check_aria_attributes(block_text)

                self.logger.debug(
                    f"[2025-02-16 15:24:34] Accessibility checked at cursor by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:24:34] Error checking accessibility at cursor: {str(e)}"
                )

        def check_heading_structure(self, text: str):
            """
            Check heading structure and hierarchy
            
            Args:
                text (str): The text to analyze for heading structure
            """
            try:
                if not re.search(r'<h[1-6]', text):
                    return

                # Get all headings in document
                editor = self.current_editor()
                content = editor.toPlainText()
                headings = re.finditer(r'<h([1-6])[^>]*>([^<]+)</h\1>', content)

                # Track heading levels
                previous_level = 0
                for match in headings:
                    level = int(match.group(1))

                    # Check for skipped levels
                    if previous_level > 0 and level > previous_level + 1:
                        self.show_accessibility_warning(
                            f"Heading level skipped: H{previous_level} to H{level}"
                        )

                    # Check for empty headings
                    if not match.group(2).strip():
                        self.show_accessibility_warning("Empty heading detected")

                    previous_level = level

                self.logger.debug(
                    f"[2025-02-16 15:24:34] Heading structure checked by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:24:34] Error checking heading structure: {str(e)}"
                )

        def show_accessibility_warning(self, message: str):
            """
            Display accessibility warning in the UI
            
            Args:
                message (str): The warning message to display
            """
            try:
                warning_item = QListWidgetItem(
                    QIcon(":/icons/warning.png"),
                    message
                )
                warning_item.setBackground(QColor("#fff3cd"))
                warning_item.setForeground(QColor("#856404"))

                self.accessibility_list.addItem(warning_item)

                # Show warning count in status bar
                warning_count = self.accessibility_list.count()
                self.status_bar.showMessage(
                    f"Accessibility warnings: {warning_count}",
                    5000
                )

                self.logger.debug(
                    f"[2025-02-16 15:24:34] Accessibility warning shown by {CURRENT_USER}: {message}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:24:34] Error showing accessibility warning: {str(e)}"
                )

        def clear_accessibility_highlights(self):
            """Clear all accessibility-related highlights in the editor"""
            try:
                editor = self.current_editor()
                if not editor:
                    return

                # Clear existing highlights
                editor.setExtraSelections([])

                # Clear accessibility warnings list
                self.accessibility_list.clear()

                self.logger.debug(
                    f"[2025-02-16 15:25:29] Accessibility highlights cleared by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error clearing accessibility highlights: {str(e)}"
                )

        def check_color_contrast(self):
            """Check color contrast ratios for accessibility"""
            try:
                editor = self.current_editor()
                if not editor:
                    return

                content = editor.toPlainText()

                # Find all color definitions
                color_patterns = [
                    r'color:\s*#[0-9a-fA-F]{6}',
                    r'background-color:\s*#[0-9a-fA-F]{6}',
                    r'color:\s*rgb\(\d+,\s*\d+,\s*\d+\)',
                    r'background-color:\s*rgb\(\d+,\s*\d+,\s*\d+\)'
                ]

                for pattern in color_patterns:
                    for match in re.finditer(pattern, content):
                        color_value = self.extract_color_value(match.group())
                        if color_value:
                            self.check_contrast_ratio(color_value)

                self.logger.debug(
                    f"[2025-02-16 15:25:29] Color contrast check completed by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error checking color contrast: {str(e)}"
                )

        def extract_color_value(self, color_def: str) -> Optional[QColor]:
            """
            Extract color value from CSS color definition
            
            Args:
                color_def (str): CSS color definition string
                
            Returns:
                Optional[QColor]: QColor object or None if invalid
            """
            try:
                # Extract hex color
                hex_match = re.search(r'#([0-9a-fA-F]{6})', color_def)
                if hex_match:
                    return QColor(f"#{hex_match.group(1)}")

                # Extract RGB color
                rgb_match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', color_def)
                if rgb_match:
                    r, g, b = map(int, rgb_match.groups())
                    return QColor(r, g, b)

                return None

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error extracting color value: {str(e)}"
                )
                return None

        def check_contrast_ratio(self, color: QColor):
            """
            Check contrast ratio against common background colors
            
            Args:
                color (QColor): The color to check
            """
            try:
                backgrounds = {
                    'White': QColor('#FFFFFF'),
                    'Light Gray': QColor('#F8F9FA'),
                    'Dark Theme': QColor('#212529')
                }

                for bg_name, bg_color in backgrounds.items():
                    ratio = self.calculate_contrast_ratio(color, bg_color)

                    # WCAG 2.1 Level AA requirements
                    if ratio < 4.5:  # minimum for normal text
                        self.show_accessibility_warning(
                            f"Low contrast ratio ({ratio:.2f}:1) with {bg_name} background"
                        )

                self.logger.debug(
                    f"[2025-02-16 15:25:29] Contrast ratio checked by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error checking contrast ratio: {str(e)}"
                )

        def calculate_contrast_ratio(self, color1: QColor, color2: QColor) -> float:
            """
            Calculate contrast ratio between two colors
            
            Args:
                color1 (QColor): First color
                color2 (QColor): Second color
                
            Returns:
                float: Contrast ratio between the colors
            """
            try:
                # Calculate relative luminance
                l1 = self.get_relative_luminance(color1)
                l2 = self.get_relative_luminance(color2)

                # Calculate contrast ratio
                lighter = max(l1, l2)
                darker = min(l1, l2)

                return (lighter + 0.05) / (darker + 0.05)

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error calculating contrast ratio: {str(e)}"
                )
                return 0.0

        def get_relative_luminance(self, color: QColor) -> float:
            """
            Calculate relative luminance of a color
            
            Args:
                color (QColor): The color to calculate luminance for
                
            Returns:
                float: Relative luminance value
            """
            try:
                # Get RGB values (0-1 range)
                r = color.redF()
                g = color.greenF()
                b = color.blueF()

                # Convert to sRGB
                r = self.to_srgb(r)
                g = self.to_srgb(g)
                b = self.to_srgb(b)

                # Calculate luminance
                return 0.2126 * r + 0.7152 * g + 0.0722 * b

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error calculating relative luminance: {str(e)}"
                )
                return 0.0

        def to_srgb(self, value: float) -> float:
            """
            Convert linear RGB value to sRGB
            
            Args:
                value (float): Linear RGB value
                
            Returns:
                float: sRGB value
            """
            try:
                if value <= 0.03928:
                    return value / 12.92
                return ((value + 0.055) / 1.055) ** 2.4

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error converting to sRGB: {str(e)}"
                )
                return 0.0

        def check_semantic_structure(self, text: str):
            """
            Check semantic structure of HTML content
            
            Args:
                text (str): The text to analyze
            """
            try:
                # Check for semantic elements
                semantic_elements = {
                    'header': '<header',
                    'nav': '<nav',
                    'main': '<main',
                    'article': '<article',
                    'section': '<section',
                    'aside': '<aside',
                    'footer': '<footer'
                }

                editor = self.current_editor()
                if not editor:
                    return

                content = editor.toPlainText()

                # Check for missing semantic elements
                missing_elements = []
                for element, tag in semantic_elements.items():
                    if tag not in content:
                        missing_elements.append(element)

                if missing_elements:
                    self.show_accessibility_warning(
                        f"Missing semantic elements: {', '.join(missing_elements)}"
                    )

                # Check for proper nesting
                self.check_semantic_nesting(content)

                self.logger.debug(
                    f"[2025-02-16 15:25:29] Semantic structure checked by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:25:29] Error checking semantic structure: {str(e)}"
                )

        def check_semantic_nesting(self, content: str):
            """
            Check proper nesting of semantic elements
            
            Args:
                content (str): HTML content to analyze
            """
            try:
                # Define valid nesting rules
                nesting_rules = {
                    'header': ['nav', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'],
                    'nav': ['ul', 'ol', 'menu'],
                    'main': ['article', 'section', 'div'],
                    'article': ['header', 'section', 'footer'],
                    'section': ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
                }

                soup = BeautifulSoup(content, 'html.parser')

                for element, expected_children in nesting_rules.items():
                    elements = soup.find_all(element)
                    for elem in elements:
                        direct_children = [child.name for child in elem.find_all(recursive=False)]
                        missing = [child for child in expected_children
                                   if child not in direct_children]

                        if missing:
                            self.show_accessibility_warning(
                                f"<{element}> missing recommended elements: {', '.join(missing)}"
                            )

                self.logger.debug(
                    f"[2025-02-16 15:32:13] Semantic nesting checked by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:32:13] Error checking semantic nesting: {str(e)}"
                )

        def check_aria_attributes(self, text: str):
            """
            Check ARIA attributes for proper usage
            
            Args:
                text (str): The text to analyze
            """
            try:
                # Common ARIA patterns to check
                aria_patterns = {
                    'role': r'role=[\'"](.*?)[\'"]',
                    'aria-label': r'aria-label=[\'"](.*?)[\'"]',
                    'aria-describedby': r'aria-describedby=[\'"](.*?)[\'"]',
                    'aria-hidden': r'aria-hidden=[\'"](.*?)[\'"]'
                }

                # Check each pattern
                for attr, pattern in aria_patterns.items():
                    matches = re.finditer(pattern, text)
                    for match in matches:
                        value = match.group(1)
                        self.validate_aria_attribute(attr, value)

                # Check for missing required ARIA attributes
                self.check_required_aria_attributes(text)

                self.logger.debug(
                    f"[2025-02-16 15:32:13] ARIA attributes checked by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:32:13] Error checking ARIA attributes: {str(e)}"
                )

        def validate_aria_attribute(self, attr: str, value: str):
            """
            Validate specific ARIA attribute values
            
            Args:
                attr (str): The ARIA attribute name
                value (str): The attribute value to validate
            """
            try:
                if attr == 'role':
                    valid_roles = {
                        'button', 'link', 'heading', 'navigation', 'main',
                        'complementary', 'banner', 'contentinfo', 'search'
                    }
                    if value not in valid_roles:
                        self.show_accessibility_warning(f"Invalid role value: {value}")

                elif attr == 'aria-label':
                    if not value.strip():
                        self.show_accessibility_warning("Empty aria-label value")

                elif attr == 'aria-describedby':
                    if not self.check_id_reference(value):
                        self.show_accessibility_warning(
                            f"aria-describedby reference not found: {value}"
                        )

                elif attr == 'aria-hidden':
                    if value not in ('true', 'false'):
                        self.show_accessibility_warning(
                            f"Invalid aria-hidden value: {value}"
                        )

                self.logger.debug(
                    f"[2025-02-16 15:32:13] Validated ARIA attribute {attr} by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:32:13] Error validating ARIA attribute: {str(e)}"
                )

        def check_id_reference(self, id_ref: str) -> bool:
            """
            Check if an ID reference exists in the document
            
            Args:
                id_ref (str): The ID to check for
                
            Returns:
                bool: True if ID exists, False otherwise
            """
            try:
                editor = self.current_editor()
                if not editor:
                    return False

                content = editor.toPlainText()
                id_pattern = f'id=[\'\"]{id_ref}[\'\"]'

                return bool(re.search(id_pattern, content))

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:32:13] Error checking ID reference: {str(e)}"
                )
                return False

        def check_required_aria_attributes(self, text: str):
            """
            Check for required ARIA attributes on specific elements
            
            Args:
                text (str): The text to analyze
            """
            try:
                # Elements requiring specific ARIA attributes
                required_attributes = {
                    'button': ['aria-label', 'aria-pressed'],
                    'input': ['aria-label', 'aria-required'],
                    'img': ['aria-label'],
                    'dialog': ['aria-labelledby', 'aria-modal'],
                    'menuitem': ['aria-label', 'aria-selected']
                }

                for element, required_attrs in required_attributes.items():
                    element_pattern = f'<{element}[^>]*>'
                    matches = re.finditer(element_pattern, text)

                    for match in matches:
                        element_text = match.group()
                        missing_attrs = []

                        for attr in required_attrs:
                            if attr not in element_text:
                                missing_attrs.append(attr)

                        if missing_attrs:
                            self.show_accessibility_warning(
                                f"<{element}> missing required ARIA attributes: "
                                f"{', '.join(missing_attrs)}"
                            )

                self.logger.debug(
                    f"[2025-02-16 15:32:13] Required ARIA attributes checked by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:32:13] Error checking required ARIA attributes: {str(e)}"
                )

        def update_validation_suggestions(self, suggestions: List[str]):
            """
            Update validation suggestions in the UI
            
            Args:
                suggestions (List[str]): List of validation suggestions to display
            """
            try:
                # Clear previous suggestions
                self.validation_list.clear()

                # Add new suggestions
                for suggestion in suggestions:
                    item = QListWidgetItem(
                        QIcon(":/icons/suggestion.png"),
                        suggestion
                    )
                    item.setBackground(QColor("#e2e3e5"))
                    item.setForeground(QColor("#383d41"))
                    self.validation_list.addItem(item)

                # Update suggestion count
                suggestion_count = len(suggestions)
                if suggestion_count > 0:
                    self.validation_group.setTitle(
                        f"Validation Suggestions ({suggestion_count})"
                    )
                else:
                    self.validation_group.setTitle("Validation Suggestions")

                self.logger.debug(
                    f"[2025-02-16 15:32:13] Updated validation suggestions: "
                    f"{suggestion_count} items by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:32:13] Error updating validation suggestions: {str(e)}"
                )

        def update_form_validation(self, tag_context: Dict):
            """
            Update form validation tools and suggestions
            
            Args:
                tag_context (Dict): Dictionary containing tag information and attributes
            """
            try:
                tag_name = tag_context['name']
                attrs = tag_context['attributes']

                if tag_name == 'input':
                    input_type = attrs.get('type', 'text')
                    self.update_input_validation(input_type, attrs)
                elif tag_name == 'form':
                    self.update_form_validation_methods(attrs)
                elif tag_name in ('select', 'textarea'):
                    self.update_field_validation(tag_name, attrs)

                self.logger.debug(
                    f"[2025-02-16 15:33:04] Form validation updated by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:33:04] Error updating form validation: {str(e)}"
                )

        def update_input_validation(self, input_type: str, attrs: Dict):
            """
            Update input-specific validation tools and suggestions
            
            Args:
                input_type (str): Type of input element
                attrs (Dict): Dictionary of input attributes
            """
            try:
                suggestions = []

                # Basic validation checks
                if 'required' not in attrs:
                    suggestions.append("Consider adding required attribute")

                if 'name' not in attrs:
                    suggestions.append("Input should have a name attribute")

                # Type-specific validation
                if input_type == 'email':
                    if 'pattern' not in attrs:
                        suggestions.append(
                            "Consider adding email pattern validation"
                        )
                    if 'multiple' in attrs and 'placeholder' not in attrs:
                        suggestions.append(
                            "Add placeholder for multiple email format"
                        )

                elif input_type == 'password':
                    if 'minlength' not in attrs:
                        suggestions.append(
                            "Consider adding minimum password length"
                        )
                    if 'pattern' not in attrs:
                        suggestions.append(
                            "Consider adding password strength pattern"
                        )
                    if 'autocomplete' not in attrs:
                        suggestions.append(
                            "Consider adding autocomplete attribute"
                        )

                elif input_type in ('number', 'range'):
                    if 'min' not in attrs or 'max' not in attrs:
                        suggestions.append("Consider adding min/max values")
                    if 'step' not in attrs:
                        suggestions.append("Consider adding step attribute")

                elif input_type == 'file':
                    if 'accept' not in attrs:
                        suggestions.append("Specify accepted file types")
                    if 'multiple' in attrs and 'data-max-size' not in attrs:
                        suggestions.append("Consider adding maximum file size limit")

                # Accessibility validation
                if 'aria-label' not in attrs and 'aria-labelledby' not in attrs:
                    suggestions.append("Add accessible label")

                # Update validation suggestions
                self.update_validation_suggestions(suggestions)

                self.logger.debug(
                    f"[2025-02-16 15:33:04] Input validation updated for {input_type} by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:33:04] Error updating input validation: {str(e)}"
                )

        def update_form_validation_methods(self, attrs: Dict):
            """
            Update form validation method suggestions
            
            Args:
                attrs (Dict): Dictionary of form attributes
            """
            try:
                suggestions = []

                # Basic form attributes
                if 'novalidate' in attrs:
                    suggestions.append("Form validation is disabled (novalidate)")

                if 'method' not in attrs:
                    suggestions.append("Form method not specified")
                elif attrs['method'].lower() not in ('get', 'post'):
                    suggestions.append("Invalid form method specified")

                if 'action' not in attrs:
                    suggestions.append("Form action not specified")

                # Security checks
                if attrs.get('method', '').lower() == 'post':
                    if not self.has_csrf_protection():
                        suggestions.append("Add CSRF protection")
                    if 'enctype' not in attrs and self.has_file_inputs():
                        suggestions.append(
                            "Add multipart/form-data enctype for file uploads"
                        )

                # Accessibility checks
                if 'name' not in attrs:
                    suggestions.append("Add form name attribute")
                if 'aria-label' not in attrs and 'aria-labelledby' not in attrs:
                    suggestions.append("Add accessible form label")

                # Client-side validation
                if not self.has_client_validation():
                    suggestions.append("Consider adding client-side validation")

                # Update validation suggestions
                self.update_validation_suggestions(suggestions)

                self.logger.debug(
                    f"[2025-02-16 15:33:04] Form validation methods updated by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:33:04] Error updating form validation methods: {str(e)}"
                )

        def has_client_validation(self) -> bool:
            """
            Check if form has client-side validation
            
            Returns:
                bool: True if client validation exists, False otherwise
            """
            try:
                editor = self.current_editor()
                if not editor:
                    return False

                content = editor.toPlainText()

                # Check for common validation patterns
                validation_patterns = [
                    r'onsubmit=[\'"](.*?validation.*?)[\'"]',
                    r'<script[^>]*>(.*?validate.*?)</script>',
                    r'data-validate',
                    r'class=[\'"](.*?validate.*?)[\'"]'
                ]

                return any(re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                           for pattern in validation_patterns)

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:33:04] Error checking client validation: {str(e)}"
                )
                return False

        def has_file_inputs(self) -> bool:
            """
            Check if form has file input elements
            
            Returns:
                bool: True if file inputs exist, False otherwise
            """
            try:
                editor = self.current_editor()
                if not editor:
                    return False

                content = editor.toPlainText()

                # Check for file input elements
                return bool(re.search(r'<input[^>]+type=[\'"]file[\'"]', content))

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:33:04] Error checking file inputs: {str(e)}"
                )
                return False


    def check_color_contrast(self):
        """
        Check color contrast ratios for accessibility
        Last modified: 2025-02-16 15:36:17
        Modified by: vcutrone
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            cursor = editor.textCursor()
            block_text = cursor.block().text()

            # Find color definitions with optimized patterns
            color_patterns = (
                r'color:\s*#[0-9a-fA-F]{6}',
                r'background-color:\s*#[0-9a-fA-F]{6}',
                r'color:\s*rgb\(\d+,\s*\d+,\s*\d+\)',
                r'background-color:\s*rgb\(\d+,\s*\d+,\s*\d+\)'
            )

            # Compile patterns for better performance
            compiled_patterns = [re.compile(pattern) for pattern in color_patterns]

            for pattern in compiled_patterns:
                matches = pattern.finditer(block_text)
                for match in matches:
                    color_value = self.extract_color_value(match.group())
                    if color_value:
                        self.check_contrast_ratio(color_value)

            self.logger.debug(
                f"[2025-02-16 15:36:17] Color contrast check completed by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:36:17] Error checking color contrast: {str(e)}"
            )


    def extract_color_value(self, color_def: str) -> Optional[Tuple[int, int, int]]:
        """
        Extract RGB values from color definition
        
        Args:
            color_def (str): CSS color definition string
            
        Returns:
            Optional[Tuple[int, int, int]]: RGB color values or None if invalid
        """
        try:
            # Optimized hex color pattern
            hex_pattern = re.compile(r'#([0-9a-fA-F]{6})')
            hex_match = hex_pattern.search(color_def)
            if hex_match:
                hex_value = hex_match.group(1)
                return (
                    int(hex_value[0:2], 16),
                    int(hex_value[2:4], 16),
                    int(hex_value[4:6], 16)
                )

            # Optimized RGB color pattern
            rgb_pattern = re.compile(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)')
            rgb_match = rgb_pattern.search(color_def)
            if rgb_match:
                return tuple(map(int, rgb_match.groups()))

            return None

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:36:17] Error extracting color value: {str(e)}"
            )
            return None


    def check_contrast_ratio(self, color: Tuple[int, int, int]):
        """
        Check if color contrast meets WCAG guidelines
        
        Args:
            color (Tuple[int, int, int]): RGB color values
        """
        try:
            def get_luminance(r: int, g: int, b: int) -> float:
                """Calculate relative luminance from RGB values"""
                rs, gs, bs = r / 255, g / 255, b / 255

                # Optimized luminance calculation
                rs = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
                gs = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
                bs = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4

                return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs

            # Use white background as default
            background = (255, 255, 255)

            # Calculate contrast ratio
            l1 = get_luminance(*color)
            l2 = get_luminance(*background)

            ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

            # Check against WCAG guidelines with specific warnings
            if ratio < 4.5:  # AA standard for normal text
                self.show_accessibility_warning(
                    f"Low contrast ratio ({ratio:.2f}:1) - "
                    f"Minimum required: 4.5:1 for normal text"
                )
            elif ratio < 7:  # AAA standard
                self.show_accessibility_warning(
                    f"Moderate contrast ratio ({ratio:.2f}:1) - "
                    f"Consider improving for AAA compliance"
                )

            self.logger.debug(
                f"[2025-02-16 15:36:17] Contrast ratio checked by {CURRENT_USER}: {ratio:.2f}:1"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:36:17] Error checking contrast ratio: {str(e)}"
            )

        def check_color_contrast(self):
            """
            Check color contrast ratios for accessibility
            Last modified: 2025-02-16 15:36:17
            Modified by: vcutrone
            """

        try:
            editor = self.current_editor()
            if not editor:
                return

            cursor = editor.textCursor()
            block_text = cursor.block().text()

            # Find color definitions with optimized patterns
            color_patterns = (
                r'color:\s*#[0-9a-fA-F]{6}',
                r'background-color:\s*#[0-9a-fA-F]{6}',
                r'color:\s*rgb\(\d+,\s*\d+,\s*\d+\)',
                r'background-color:\s*rgb\(\d+,\s*\d+,\s*\d+\)'
            )

            # Compile patterns for better performance
            compiled_patterns = [re.compile(pattern) for pattern in color_patterns]

            for pattern in compiled_patterns:
                matches = pattern.finditer(block_text)
                for match in matches:
                    color_value = self.extract_color_value(match.group())
                    if color_value:
                        self.check_contrast_ratio(color_value)

            self.logger.debug(
                f"[2025-02-16 15:36:17] Color contrast check completed by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:36:17] Error checking color contrast: {str(e)}"
            )


    def extract_color_value(self, color_def: str) -> Optional[Tuple[int, int, int]]:
        """
        Extract RGB values from color definition
        
        Args:
            color_def (str): CSS color definition string
            
        Returns:
            Optional[Tuple[int, int, int]]: RGB color values or None if invalid
        """
        try:
            # Optimized hex color pattern
            hex_pattern = re.compile(r'#([0-9a-fA-F]{6})')
            hex_match = hex_pattern.search(color_def)
            if hex_match:
                hex_value = hex_match.group(1)
                return (
                    int(hex_value[0:2], 16),
                    int(hex_value[2:4], 16),
                    int(hex_value[4:6], 16)
                )

            # Optimized RGB color pattern
            rgb_pattern = re.compile(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)')
            rgb_match = rgb_pattern.search(color_def)
            if rgb_match:
                return tuple(map(int, rgb_match.groups()))

            return None

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:36:17] Error extracting color value: {str(e)}"
            )
            return None


    def check_contrast_ratio(self, color: Tuple[int, int, int]):
        """
        Check if color contrast meets WCAG guidelines
        
        Args:
            color (Tuple[int, int, int]): RGB color values
        """
        try:
            def get_luminance(r: int, g: int, b: int) -> float:
                """Calculate relative luminance from RGB values"""
                rs, gs, bs = r / 255, g / 255, b / 255

                # Optimized luminance calculation
                rs = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
                gs = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
                bs = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4

                return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs

            # Use white background as default
            background = (255, 255, 255)

            # Calculate contrast ratio
            l1 = get_luminance(*color)
            l2 = get_luminance(*background)

            ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

            # Check against WCAG guidelines with specific warnings
            if ratio < 4.5:  # AA standard for normal text
                self.show_accessibility_warning(
                    f"Low contrast ratio ({ratio:.2f}:1) - "
                    f"Minimum required: 4.5:1 for normal text"
                )
            elif ratio < 7:  # AAA standard
                self.show_accessibility_warning(
                    f"Moderate contrast ratio ({ratio:.2f}:1) - "
                    f"Consider improving for AAA compliance"
                )

            self.logger.debug(
                f"[2025-02-16 15:36:17] Contrast ratio checked by {CURRENT_USER}: {ratio:.2f}:1"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:36:17] Error checking contrast ratio: {str(e)}"
            )


    def check_semantic_structure(self, text: str):
        """
        Check semantic HTML structure and provide recommendations
        
        Args:
            text (str): HTML content to analyze
        
        Last modified: 2025-02-16 15:37:05
        Modified by: vcutrone
        """
        try:
            warnings = []

            # Semantic element mappings with descriptions
            semantic_mappings = {
                '<div class="header"': {
                    'suggested': '<header>',
                    'reason': 'semantic landmark element'
                },
                '<div class="footer"': {
                    'suggested': '<footer>',
                    'reason': 'semantic landmark element'
                },
                '<div class="nav"': {
                    'suggested': '<nav>',
                    'reason': 'navigation landmark'
                },
                '<div class="main"': {
                    'suggested': '<main>',
                    'reason': 'main content landmark'
                },
                '<div class="aside"': {
                    'suggested': '<aside>',
                    'reason': 'complementary content'
                }
            }

            # Check semantic elements usage
            for div_pattern, semantic_info in semantic_mappings.items():
                if div_pattern in text:
                    warnings.append(
                        f"Consider using {semantic_info['suggested']} instead of "
                        f"{div_pattern} for better {semantic_info['reason']}"
                    )

            # Check list structure with optimized regex
            list_pattern = re.compile(r'<div[^>]*>(?:(?:<br>|\n)\s*[-•].*?)+</div>')
            if list_pattern.search(text):
                warnings.append(
                    "Convert bullet points to proper <ul> or <ol> list structure"
                )

            # Check heading hierarchy
            self.check_heading_hierarchy(text, warnings)

            # Check ARIA landmarks
            self.check_aria_landmarks(text, warnings)

            # Add warnings to UI
            for warning in warnings:
                self.show_accessibility_warning(warning)

            self.logger.debug(
                f"[2025-02-16 15:37:05] Semantic structure checked by {CURRENT_USER}: "
                f"{len(warnings)} issues found"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:37:05] Error checking semantic structure: {str(e)}"
            )


    def check_heading_hierarchy(self, text: str, warnings: List[str]):
        """
        Check proper heading hierarchy
        
        Args:
            text (str): HTML content to analyze
            warnings (List[str]): List to append warnings to
        """
        try:
            # Find all headings
            heading_pattern = re.compile(r'<h([1-6])[^>]*>(.*?)</h\1>', re.DOTALL)
            headings = heading_pattern.finditer(text)

            current_level = 0
            for match in headings:
                level = int(match.group(1))
                content = match.group(2).strip()

                # Check for empty headings
                if not content:
                    warnings.append(f"Empty heading found: <h{level}></h{level}>")
                    continue

                # Check heading hierarchy
                if current_level == 0 and level != 1:
                    warnings.append(
                        f"Document should start with h1, found h{level}"
                    )
                elif level > current_level + 1:
                    warnings.append(
                        f"Heading level skipped: h{current_level} to h{level}"
                    )

                current_level = level

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:37:05] Error checking heading hierarchy: {str(e)}"
            )


    def check_aria_landmarks(self, text: str, warnings: List[str]):
        """
        Check ARIA landmarks and roles
        
        Args:
            text (str): HTML content to analyze
            warnings (List[str]): List to append warnings to
        """
        try:
            # Required landmarks
            required_landmarks = {
                'banner': False,
                'navigation': False,
                'main': False,
                'contentinfo': False
            }

            # Check for landmarks
            for landmark in required_landmarks:
                pattern = f'role=[\'"]{landmark}[\'"]'
                if re.search(pattern, text):
                    required_landmarks[landmark] = True

            # Check semantic elements that imply landmarks
            semantic_mapping = {
                '<header>': 'banner',
                '<nav>': 'navigation',
                '<main>': 'main',
                '<footer>': 'contentinfo'
            }

            for element, landmark in semantic_mapping.items():
                if element in text:
                    required_landmarks[landmark] = True

            # Add warnings for missing landmarks
            for landmark, present in required_landmarks.items():
                if not present:
                    warnings.append(
                        f"Missing {landmark} landmark - Add either semantic element "
                        f"or role=\"{landmark}\""
                    )

            self.logger.debug(
                f"[2025-02-16 15:37:05] ARIA landmarks checked by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:37:05] Error checking ARIA landmarks: {str(e)}"
            )


    def check_aria_attributes(self, text: str):
        """
        Check ARIA attributes usage and validity
        
        Args:
            text (str): HTML content to analyze
        """
        try:
            # Load ARIA validation data
            aria_data = self.load_aria_validation_data()

            # Check ARIA roles
            role_pattern = re.compile(r'role=["\']([^"\']+)["\']')
            for match in role_pattern.finditer(text):
                role = match.group(1)
                self.validate_aria_role(role, aria_data['roles'])

            # Check ARIA attributes
            attr_pattern = re.compile(r'aria-[\w-]+=["\'][^"\']*["\']')
            for match in attr_pattern.finditer(text):
                attr = match.group()
                self.validate_aria_attribute(attr, aria_data['attributes'])

            self.logger.debug(
                f"[2025-02-16 15:37:05] ARIA attributes checked by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:37:05] Error checking ARIA attributes: {str(e)}"
            )


    def load_aria_validation_data(self) -> Dict:
        """
        Load ARIA validation data from configuration files
        
        Returns:
            Dict: Dictionary containing ARIA roles and attributes validation data
        
        Last modified: 2025-02-16 15:38:15
        Modified by: vcutrone
        """
        try:
            aria_data = {
                'roles': {},
                'attributes': {}
            }

            # Load ARIA roles data
            roles_path = os.path.join(
                self.config_dir,
                "resources/aria/roles.json"
            )
            if os.path.exists(roles_path):
                with open(roles_path, 'r', encoding='utf-8') as f:
                    aria_data['roles'] = json.load(f)

            # Load ARIA attributes data
            attrs_path = os.path.join(
                self.config_dir,
                "resources/aria/attributes.json"
            )
            if os.path.exists(attrs_path):
                with open(attrs_path, 'r', encoding='utf-8') as f:
                    aria_data['attributes'] = json.load(f)

            self.logger.debug(
                f"[2025-02-16 15:38:15] ARIA validation data loaded by {CURRENT_USER}"
            )
            return aria_data

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:38:15] Error loading ARIA validation data: {str(e)}"
            )
            return {'roles': {}, 'attributes': {}}


    def validate_aria_role(self, role: str, valid_roles: Dict):
        """
        Validate ARIA role against specifications
        
        Args:
            role (str): ARIA role to validate
            valid_roles (Dict): Dictionary of valid ARIA roles and their requirements
        """
        try:
            if role not in valid_roles:
                self.show_accessibility_warning(
                    f"Invalid ARIA role: '{role}'"
                )
                return

            role_data = valid_roles[role]

            # Check required attributes
            if 'required_attrs' in role_data:
                editor = self.current_editor()
                if editor:
                    content = editor.toPlainText()
                    for attr in role_data['required_attrs']:
                        if f'aria-{attr}' not in content:
                            self.show_accessibility_warning(
                                f"Role '{role}' requires attribute 'aria-{attr}'"
                            )

            # Check required parent roles
            if 'required_parent' in role_data:
                self.check_parent_roles(role, role_data['required_parent'])

            self.logger.debug(
                f"[2025-02-16 15:38:15] Validated ARIA role '{role}' by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:38:15] Error validating ARIA role: {str(e)}"
            )


    def validate_aria_attribute(self, attr: str, valid_attributes: Dict):
        """
        Validate ARIA attribute usage and value
        
        Args:
            attr (str): ARIA attribute to validate
            valid_attributes (Dict): Dictionary of valid ARIA attributes and their requirements
        """
        try:
            # Extract attribute name and value
            match = re.match(r'(aria-[\w-]+)=["\']([^"\']*)["\']', attr)
            if not match:
                return

            attr_name, attr_value = match.groups()

            if attr_name not in valid_attributes:
                self.show_accessibility_warning(
                    f"Invalid ARIA attribute: '{attr_name}'"
                )
                return

            attr_data = valid_attributes[attr_name]

            # Validate value type
            if 'value_type' in attr_data:
                self.validate_aria_value(
                    attr_name,
                    attr_value,
                    attr_data['value_type']
                )

            # Check for deprecated attributes
            if attr_data.get('deprecated', False):
                self.show_accessibility_warning(
                    f"Deprecated ARIA attribute: '{attr_name}'. "
                    f"Use '{attr_data.get('alternative', '')}' instead."
                )

            self.logger.debug(
                f"[2025-02-16 15:38:15] Validated ARIA attribute '{attr_name}' by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:38:15] Error validating ARIA attribute: {str(e)}"
            )


    def validate_aria_value(self, attr_name: str, value: str, value_type: str):
        """
        Validate ARIA attribute value based on its type
        
        Args:
            attr_name (str): Name of the ARIA attribute
            value (str): Value to validate
            value_type (str): Expected type of the value
        """
        try:
            if value_type == 'boolean':
                if value not in ('true', 'false'):
                    self.show_accessibility_warning(
                        f"Invalid boolean value for {attr_name}: '{value}'. "
                        f"Use 'true' or 'false'."
                    )

            elif value_type == 'id-reference':
                if not self.check_id_exists(value):
                    self.show_accessibility_warning(
                        f"ID reference '{value}' in {attr_name} not found in document"
                    )

            elif value_type == 'number':
                try:
                    float(value)
                except ValueError:
                    self.show_accessibility_warning(
                        f"Invalid number value for {attr_name}: '{value}'"
                    )

            elif value_type == 'token':
                if not re.match(r'^[\w-]+$', value):
                    self.show_accessibility_warning(
                        f"Invalid token value for {attr_name}: '{value}'"
                    )

            self.logger.debug(
                f"[2025-02-16 15:38:15] Validated ARIA value type '{value_type}' by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:38:15] Error validating ARIA value: {str(e)}"
            )


    def check_id_exists(self, id_value: str) -> bool:
        """
        Check if an ID exists in the document
        
        Args:
            id_value (str): ID to check for
            
        Returns:
            bool: True if ID exists, False otherwise
        """
        try:
            editor = self.current_editor()
            if not editor:
                return False

            content = editor.toPlainText()
            return bool(re.search(f'id=["\'{id_value}["\']', content))

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:38:15] Error checking ID existence: {str(e)}"
            )
            return False


    def check_parent_roles(self, role: str, required_parents: List[str]):
        """
        Check if element with role has required parent roles
        
        Args:
            role (str): Role to check
            required_parents (List[str]): List of valid parent roles
        
        Last modified: 2025-02-16 15:39:16
        Modified by: vcutrone
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            content = editor.toPlainText()

            # Find element with role
            role_match = re.search(
                f'<([^>]+)\\srole=["\'{role}["\']([^>]*)>',
                content
            )
            if not role_match:
                return

            # Check parent elements
            start_pos = role_match.start()
            parent_content = content[:start_pos]

            has_valid_parent = False
            for parent_role in required_parents:
                if f'role="{parent_role}"' in parent_content:
                    has_valid_parent = True
                    break

            if not has_valid_parent:
                self.show_accessibility_warning(
                    f"Role '{role}' requires a parent element with one of these "
                    f"roles: {', '.join(required_parents)}"
                )

            self.logger.debug(
                f"[2025-02-16 15:39:16] Checked parent roles for '{role}' by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:39:16] Error checking parent roles: {str(e)}"
            )


    def clear_accessibility_highlights(self):
        """
        Clear all accessibility-related highlights and warnings
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Clear editor highlights
            editor.setExtraSelections([])

            # Clear warning list
            self.accessibility_list.clear()

            # Reset warning count
            self.update_accessibility_status("No accessibility issues")

            self.logger.debug(
                f"[2025-02-16 15:39:16] Accessibility highlights cleared by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:39:16] Error clearing accessibility highlights: {str(e)}"
            )


    def update_accessibility_status(self, message: str):
        """
        Update accessibility status in the status bar
        
        Args:
            message (str): Status message to display
        """
        try:
            self.status_bar.showMessage(
                f"Accessibility: {message}",
                5000  # Show for 5 seconds
            )

            self.logger.debug(
                f"[2025-02-16 15:39:16] Accessibility status updated by {CURRENT_USER}: {message}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:39:16] Error updating accessibility status: {str(e)}"
            )


    def handle_git_operation_complete(self, operation: str, success: bool):
        """
        Handle completion of Git operations
        
        Args:
            operation (str): Name of the Git operation
            success (bool): Whether the operation was successful
        """
        try:
            if success:
                self.show_status_message(
                    f"Git {operation} completed successfully"
                )
                self.update_git_status()
            else:
                self.show_error_message(
                    f"Git {operation} failed. Check Git panel for details."
                )

            # Update UI elements
            self.git_toolbar.setEnabled(True)
            self.update_git_indicators()

            # Log operation completion
            log_level = "info" if success else "error"
            getattr(self.logger, log_level)(
                f"[2025-02-16 15:39:16] Git {operation} completed "
                f"(success: {success}) by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:39:16] Error handling git operation completion: {str(e)}"
            )


    def update_git_indicators(self):
        """Update Git status indicators in the editor"""
        try:
            editor = self.current_editor()
            if not editor or not self.git_manager.is_repo():
                return

            # Get current file status
            current_file = self.get_current_file()
            if not current_file:
                return

            status = self.git_manager.get_file_status(current_file)

            # Update indicators
            self.update_git_line_indicators(editor, status)
            self.update_git_margin_indicators(status)

            # Update status bar
            if status.get('modified', False):
                self.show_status_message("File has uncommitted changes")

            self.logger.debug(
                f"[2025-02-16 15:39:16] Git indicators updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:39:16] Error updating git indicators: {str(e)}"
            )


    def update_git_line_indicators(self, editor: QTextEdit, status: Dict):
        """
        Update Git line change indicators
        
        Args:
            editor (QTextEdit): The editor instance
            status (Dict): Git status information
        """
        try:
            selections = []

            if 'lines' in status:
                for line_num, change_type in status['lines'].items():
                    selection = self.create_git_line_selection(
                        editor,
                        line_num,
                        change_type
                    )
                    if selection:
                        selections.append(selection)

            editor.setExtraSelections(selections)

            self.logger.debug(
                f"[2025-02-16 15:39:16] Git line indicators updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:39:16] Error updating git line indicators: {str(e)}"
            )


    def create_git_line_selection(
            self,
            editor: QTextEdit,
            line_num: int,
            change_type: str
    ) -> Optional[QTextEdit.ExtraSelection]:
        """
        Create a selection for Git line indicators
        
        Args:
            editor (QTextEdit): The editor instance
            line_num (int): Line number
            change_type (str): Type of change ('added', 'modified', 'deleted')
            
        Returns:
            Optional[QTextEdit.ExtraSelection]: Selection object or None if invalid
        
        Last modified: 2025-02-16 15:40:20
        Modified by: vcutrone
        """
        try:
            selection = QTextEdit.ExtraSelection()
            cursor = editor.textCursor()

            # Move cursor to line
            cursor.movePosition(
                QTextCursor.MoveOperation.Start,
                QTextCursor.MoveMode.MoveAnchor
            )
            for _ in range(line_num - 1):
                cursor.movePosition(
                    QTextCursor.MoveOperation.NextBlock,
                    QTextCursor.MoveMode.MoveAnchor
                )

            # Set selection format based on change type
            format = QTextCharFormat()
            colors = {
                'added': QColor("#e6ffe6"),  # Light green
                'modified': QColor("#fff5e6"),  # Light orange
                'deleted': QColor("#ffe6e6")  # Light red
            }
            format.setBackground(colors.get(change_type, QColor("#f0f0f0")))

            selection.format = format
            selection.cursor = cursor

            return selection

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:40:20] Error creating git line selection: {str(e)}"
            )
            return None


    def update_git_margin_indicators(self, status: Dict):
        """
        Update Git margin change indicators
        
        Args:
            status (Dict): Git status information
        """
        try:
            # Clear existing indicators
            self.git_margin.clear()

            if 'lines' in status:
                for line_num, change_type in status['lines'].items():
                    self.create_margin_indicator(line_num, change_type)

            self.logger.debug(
                f"[2025-02-16 15:40:20] Git margin indicators updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:40:20] Error updating git margin indicators: {str(e)}"
            )


    def create_margin_indicator(self, line_num: int, change_type: str):
        """
        Create a margin indicator for Git changes
        
        Args:
            line_num (int): Line number
            change_type (str): Type of change ('added', 'modified', 'deleted')
        """
        try:
            indicator = QWidget(self.git_margin)
            indicator.setFixedSize(16, 16)

            # Set indicator color
            colors = {
                'added': "#28a745",  # Green
                'modified': "#ffc107",  # Yellow
                'deleted': "#dc3545",  # Red
                'default': "#6c757d"  # Gray
            }
            color = colors.get(change_type, colors['default'])

            # Create indicator style
            indicator.setStyleSheet(f"""
                QWidget {{
                    background-color: {color};
                    border-radius: 8px;
                    margin: 2px;
                }}
                QWidget:hover {{
                    background-color: darker({color}, 120%);
                }}
            """)

            # Position indicator
            y_pos = (line_num - 1) * self.git_margin.fontMetrics().height()
            indicator.move(2, y_pos)
            indicator.show()

            # Add tooltip
            indicator.setToolTip(f"Line {line_num}: {change_type.title()}")

            # Connect click handler
            indicator.mousePressEvent = lambda e: self.show_git_diff_popup(line_num)

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:40:20] Error creating margin indicator: {str(e)}"
            )


    def show_git_diff_popup(self, line_num: int):
        """
        Show Git diff popup for a specific line
        
        Args:
            line_num (int): Line number to show diff for
        """
        try:
            current_file = self.get_current_file()
            if not current_file or not self.git_manager.is_repo():
                return

            # Get diff for the line
            diff = self.git_manager.get_line_diff(current_file, line_num)
            if not diff:
                self.show_status_message("No changes for this line")
                return

            # Create and configure popup
            popup = self.create_diff_popup(diff)

            # Position popup near the cursor
            cursor_pos = QCursor.pos()
            popup.setGeometry(
                cursor_pos.x() + 10,
                cursor_pos.y() + 10,
                600,
                400
            )

            popup.show()

            self.logger.debug(
                f"[2025-02-16 15:40:20] Showed git diff popup for line {line_num} by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:40:20] Error showing git diff popup: {str(e)}"
            )


    def create_diff_popup(self, diff: str) -> QDialog:
        """
        Create a popup dialog for displaying Git diffs
        
        Args:
            diff (str): Diff content to display
            
        Returns:
            QDialog: Configured dialog window
        """
        try:
            popup = QDialog(self)
            popup.setWindowTitle("Git Diff")
            popup.setModal(True)

            # Setup layout
            layout = QVBoxLayout(popup)

            # Add diff viewer
            diff_viewer = QTextEdit()
            diff_viewer.setReadOnly(True)
            diff_viewer.setFont(QFont("Courier New", 10))

            # Format and set diff content
            formatted_diff = self.format_diff_content(diff)
            diff_viewer.setHtml(formatted_diff)

            layout.addWidget(diff_viewer)

            # Add close button
            close_button = QPushButton("Close")
            close_button.clicked.connect(popup.close)
            layout.addWidget(close_button)

            return popup

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:40:20] Error creating diff popup: {str(e)}"
            )
            return QDialog(self)


    def restore_from_backup(self):
        """
        Restore file from backup
        
        Last modified: 2025-02-16 15:42:47
        Modified by: vcutrone
        """
        try:
            current_file = self.get_current_file()
            if not current_file:
                self.show_status_message("No file to restore")
                return

            # Get list of backups for current file
            filename = os.path.basename(current_file)
            backup_pattern = f"{filename}.*.bak"

            # Get sorted backup files
            backup_files = sorted([
                file for file in os.listdir(self.backup_settings['backup_dir'])
                if fnmatch.fnmatch(file, backup_pattern)
            ], reverse=True)

            if not backup_files:
                self.show_status_message("No backups found")
                return

            # Show backup selection dialog
            dialog = BackupRestoreDialog(backup_files, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            selected_backup = dialog.get_selected_backup()
            if not selected_backup:
                return

            # Load backup content
            backup_path = os.path.join(
                self.backup_settings['backup_dir'],
                selected_backup
            )

            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(backup_path, 'r', encoding='latin-1') as f:
                    content = f.read()

            # Update editor content
            editor = self.current_editor()
            if editor:
                editor.setPlainText(content)
                self.show_status_message(
                    f"Restored from backup: {selected_backup}"
                )

            self.logger.info(
                f"[2025-02-16 15:42:47] File restored from backup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:42:47] Error restoring from backup: {str(e)}"
            )


    def setup_snippet_manager(self):
        """
        Setup code snippet management system
        """
        try:
            # Initialize snippet storage with typing
            self.snippets: Dict[str, Dict] = {}
            self.snippet_categories: Set[str] = set()

            # Load snippets
            self.load_snippets()

            # Setup UI
            self.setup_snippet_toolbar()

            self.logger.info(
                f"[2025-02-16 15:42:47] Snippet manager setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:42:47] Error setting up snippet manager: {str(e)}"
            )


    def load_snippets(self):
        """Load code snippets from storage"""
        try:
            snippet_file = os.path.join(
                os.path.expanduser('~'),
                '.editor_snippets.json'
            )

            if os.path.exists(snippet_file):
                try:
                    with open(snippet_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.snippets = data.get('snippets', {})
                        self.snippet_categories = set(data.get('categories', []))
                except json.JSONDecodeError:
                    self.logger.error(
                        f"[2025-02-16 15:42:47] Invalid snippet file format"
                    )
                    return

            self.logger.debug(
                f"[2025-02-16 15:42:47] Snippets loaded by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:42:47] Error loading snippets: {str(e)}"
            )


    def save_snippets(self):
        """Save code snippets to storage"""
        try:
            snippet_file = os.path.join(
                os.path.expanduser('~'),
                '.editor_snippets.json'
            )

            data = {
                'snippets': self.snippets,
                'categories': list(self.snippet_categories)
            }

            # Create backup before saving
            if os.path.exists(snippet_file):
                backup_file = f"{snippet_file}.bak"
                shutil.copy2(snippet_file, backup_file)

            # Save with atomic write
            temp_file = f"{snippet_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            os.replace(temp_file, snippet_file)

            self.logger.debug(
                f"[2025-02-16 15:42:47] Snippets saved by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:42:47] Error saving snippets: {str(e)}"
            )


    def setup_snippet_toolbar(self):
        """
        Setup snippet management toolbar with icons and actions
        
        Last modified: 2025-02-16 15:43:49
        Modified by: vcutrone
        """
        try:
            # Create snippet toolbar with proper type hints
            self.snippet_toolbar: QToolBar = QToolBar("Snippets")
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.snippet_toolbar)

            # Add snippet actions with icons
            add_action = QAction(
                QIcon(":/icons/add.png"),
                "Add Snippet",
                self
            )
            add_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
            add_action.setStatusTip("Create a new code snippet")
            add_action.triggered.connect(self.show_add_snippet_dialog)
            self.snippet_toolbar.addAction(add_action)

            manage_action = QAction(
                QIcon(":/icons/manage.png"),
                "Manage Snippets",
                self
            )
            manage_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
            manage_action.setStatusTip("Manage existing snippets")
            manage_action.triggered.connect(self.show_manage_snippets_dialog)
            self.snippet_toolbar.addAction(manage_action)

            # Add category filter with proper typing
            self.category_combo: QComboBox = QComboBox()
            self.category_combo.setFixedWidth(200)
            self.category_combo.setEditable(False)
            self.category_combo.addItem("All Categories")
            self.category_combo.addItems(sorted(self.snippet_categories))
            self.category_combo.currentTextChanged.connect(self.filter_snippets)
            self.category_combo.setStatusTip("Filter snippets by category")
            self.snippet_toolbar.addWidget(self.category_combo)

            self.logger.debug(
                f"[2025-02-16 15:43:49] Snippet toolbar setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:43:49] Error setting up snippet toolbar: {str(e)}"
            )


    def show_add_snippet_dialog(self):
        """Show dialog to add new snippet with selected text support"""
        try:
            # Get selected text if any
            editor = self.current_editor()
            selected_text = ""
            if editor:
                cursor = editor.textCursor()
                if cursor.hasSelection():
                    selected_text = cursor.selectedText()

            # Create and configure dialog
            dialog = AddSnippetDialog(
                categories=self.snippet_categories,
                initial_content=selected_text,
                parent=self
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Validate input
                name = dialog.name_edit.text().strip()
                category = dialog.category_combo.currentText().strip()
                content = dialog.content_edit.toPlainText().strip()
                description = dialog.description_edit.text().strip()

                if not all([name, content]):
                    self.show_error_message(
                        "Snippet name and content are required"
                    )
                    return

                # Add snippet
                self.add_snippet(name, category, content, description)

            self.logger.debug(
                f"[2025-02-16 15:43:49] Add snippet dialog shown by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:43:49] Error showing add snippet dialog: {str(e)}"
            )


    def add_snippet(
            self,
            name: str,
            category: str,
            content: str,
            description: str
    ) -> bool:
        """
        Add new code snippet
        
        Args:
            name (str): Name of the snippet
            category (str): Category of the snippet
            content (str): Content of the snippet
            description (str): Description of the snippet
            
        Returns:
            bool: True if snippet was added successfully, False otherwise
        """
        try:
            # Validate inputs
            if name in self.snippets:
                self.show_error_message(f"Snippet '{name}' already exists")
                return False

            # Create snippet data
            snippet = {
                'content': content,
                'description': description,
                'category': category,
                'created': datetime.now().isoformat(),
                'modified': datetime.now().isoformat(),
                'created_by': CURRENT_USER,
                'modified_by': CURRENT_USER,
                'usage_count': 0
            }

            # Add to snippets
            self.snippets[name] = snippet

            # Update categories if needed
            if category:
                self.snippet_categories.add(category)
                current_categories = [
                    self.category_combo.itemText(i)
                    for i in range(self.category_combo.count())
                ]
                if category not in current_categories:
                    self.category_combo.addItem(category)

            # Save changes
            self.save_snippets()

            # Update UI
            self.filter_snippets(self.category_combo.currentText())
            self.show_status_message(f"Added snippet: {name}")

            self.logger.info(
                f"[2025-02-16 15:43:49] Snippet '{name}' added by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:43:49] Error adding snippet: {str(e)}"
            )
            return False


    def show_manage_snippets_dialog(self):
        """Show dialog to manage existing snippets"""
        try:
            dialog = ManageSnippetsDialog(
                snippets=self.snippets,
                categories=self.snippet_categories,
                parent=self
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Get updated data
                updated_snippets = dialog.get_updated_snippets()
                updated_categories = dialog.get_updated_categories()

                # Validate changes
                if self.validate_snippet_changes(
                        updated_snippets,
                        updated_categories
                ):
                    # Apply changes
                    self.snippets = updated_snippets
                    self.snippet_categories = updated_categories

                    # Save changes
                    self.save_snippets()

                    # Update UI
                    self.update_category_filter()
                    self.filter_snippets(self.category_combo.currentText())

            self.logger.debug(
                f"[2025-02-16 15:43:49] Manage snippets dialog shown by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:43:49] Error showing manage snippets dialog: {str(e)}"
            )


    def validate_snippet_changes(
            self,
            updated_snippets: Dict[str, Dict],
            updated_categories: Set[str]
    ) -> bool:
        """
        Validate changes to snippets and categories
        
        Args:
            updated_snippets (Dict[str, Dict]): Updated snippet data
            updated_categories (Set[str]): Updated category list
            
        Returns:
            bool: True if changes are valid, False otherwise
        
        Last modified: 2025-02-16 15:44:34
        Modified by: vcutrone
        """
        try:
            # Check for empty names
            if any(not name.strip() for name in updated_snippets):
                self.show_error_message("Snippet names cannot be empty")
                return False

            # Check for duplicate names
            if len(updated_snippets) != len(set(updated_snippets.keys())):
                self.show_error_message("Duplicate snippet names found")
                return False

            # Validate snippet data
            for name, snippet in updated_snippets.items():
                if not snippet.get('content', '').strip():
                    self.show_error_message(
                        f"Snippet '{name}' has empty content"
                    )
                    return False

                if snippet.get('category') not in updated_categories:
                    self.show_error_message(
                        f"Invalid category for snippet '{name}'"
                    )
                    return False

            self.logger.debug(
                f"[2025-02-16 15:44:34] Snippet changes validated by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:44:34] Error validating snippet changes: {str(e)}"
            )
            return False


    def update_category_filter(self):
        """Update snippet category filter dropdown"""
        try:
            current_category = self.category_combo.currentText()

            # Update combo box items
            self.category_combo.clear()
            self.category_combo.addItem("All Categories")

            # Add sorted categories
            sorted_categories = sorted(self.snippet_categories)
            self.category_combo.addItems(sorted_categories)

            # Restore previous selection if possible
            index = self.category_combo.findText(current_category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
            else:
                self.category_combo.setCurrentIndex(0)

            self.logger.debug(
                f"[2025-02-16 15:44:34] Category filter updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:44:34] Error updating category filter: {str(e)}"
            )


    def filter_snippets(self, category: str):
        """
        Filter snippets by category
        
        Args:
            category (str): Category to filter by
        """
        try:
            # Get filtered snippets
            if category == "All Categories":
                filtered_snippets = self.snippets
            else:
                filtered_snippets = {
                    name: snippet for name, snippet in self.snippets.items()
                    if snippet['category'] == category
                }

            # Update snippet menu
            self.update_snippet_menu(filtered_snippets)

            # Update status message
            count = len(filtered_snippets)
            self.show_status_message(
                f"Showing {count} snippet{'s' if count != 1 else ''} "
                f"in {category}"
            )

            self.logger.debug(
                f"[2025-02-16 15:44:34] Snippets filtered by category '{category}' "
                f"by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:44:34] Error filtering snippets: {str(e)}"
            )


    def update_snippet_menu(self, snippets: Dict[str, Dict]):
        """
        Update snippet menu with filtered snippets
        
        Args:
            snippets (Dict[str, Dict]): Filtered snippets to display
        """
        try:
            # Remove existing menu
            if hasattr(self, 'snippet_menu'):
                self.snippet_toolbar.removeAction(
                    self.snippet_menu.menuAction()
                )

            # Create new menu
            self.snippet_menu = QMenu("Insert Snippet", self)

            if not snippets:
                # Add placeholder for empty menu
                action = QAction("No snippets available", self)
                action.setEnabled(False)
                self.snippet_menu.addAction(action)
            else:
                # Add snippets sorted by name
                for name in sorted(snippets.keys()):
                    snippet = snippets[name]
                    action = QAction(name, self)

                    # Add description as tooltip
                    if snippet.get('description'):
                        action.setToolTip(snippet['description'])

                    # Add keyboard shortcut if defined
                    if 'shortcut' in snippet:
                        action.setShortcut(
                            QKeySequence(snippet['shortcut'])
                        )

                    # Connect action
                    action.triggered.connect(
                        lambda checked, n=name: self.insert_snippet(n)
                    )
                    self.snippet_menu.addAction(action)

            # Add menu to toolbar
            self.snippet_toolbar.addAction(self.snippet_menu.menuAction())

            self.logger.debug(
                f"[2025-02-16 15:44:34] Snippet menu updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:44:34] Error updating snippet menu: {str(e)}"
            )


    def insert_snippet(self, name: str) -> bool:
        """
        Insert code snippet at cursor position
        
        Args:
            name (str): Name of the snippet to insert
            
        Returns:
            bool: True if snippet was inserted successfully, False otherwise
        
        Last modified: 2025-02-16 15:45:26
        Modified by: vcutrone
        """
        try:
            editor = self.current_editor()
            if not editor:
                self.show_error_message("No active editor")
                return False

            # Get snippet content
            snippet = self.snippets.get(name)
            if not snippet:
                self.show_error_message(f"Snippet '{name}' not found")
                return False

            # Start compound undo operation
            cursor = editor.textCursor()
            cursor.beginEditBlock()

            try:
                # Handle indentation
                current_indent = self.get_current_indentation(cursor)
                content = self.adjust_snippet_indentation(
                    snippet['content'],
                    current_indent
                )

                # Insert content
                cursor.insertText(content)

                # Update snippet statistics
                self.update_snippet_statistics(name)

                self.show_status_message(f"Inserted snippet: {name}")

                self.logger.debug(
                    f"[2025-02-16 15:45:26] Snippet '{name}' inserted by {CURRENT_USER}"
                )
                return True

            finally:
                cursor.endEditBlock()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:45:26] Error inserting snippet: {str(e)}"
            )
            return False


    def get_current_indentation(self, cursor: QTextCursor) -> str:
        """
        Get current line indentation
        
        Args:
            cursor (QTextCursor): Current text cursor
            
        Returns:
            str: Current line indentation string
        """
        try:
            block = cursor.block()
            text = block.text()

            # Calculate indentation
            indent = ''
            for char in text:
                if char in ' \t':
                    indent += char
                else:
                    break

            return indent

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:45:26] Error getting indentation: {str(e)}"
            )
            return ''


    def adjust_snippet_indentation(self, content: str, indent: str) -> str:
        """
        Adjust snippet indentation to match current position
        
        Args:
            content (str): Snippet content
            indent (str): Target indentation string
            
        Returns:
            str: Adjusted snippet content
        """
        try:
            lines = content.splitlines()
            if not lines:
                return content

            # Process each line
            adjusted_lines = []
            for i, line in enumerate(lines):
                if i == 0:
                    # First line uses cursor position indentation
                    adjusted_lines.append(line)
                else:
                    # Subsequent lines maintain relative indentation
                    if line.strip():
                        adjusted_lines.append(indent + line)
                    else:
                        adjusted_lines.append(line)

            return '\n'.join(adjusted_lines)

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:45:26] Error adjusting indentation: {str(e)}"
            )
            return content


    def update_snippet_statistics(self, name: str):
        """
        Update snippet usage statistics
        
        Args:
            name (str): Name of the snippet
        """
        try:
            snippet = self.snippets.get(name)
            if not snippet:
                return

            # Update statistics
            if 'usage_count' not in snippet:
                snippet['usage_count'] = 0
            snippet['usage_count'] += 1

            snippet['last_used'] = datetime.now().isoformat()
            snippet['last_used_by'] = CURRENT_USER

            # Update modification info
            snippet['modified'] = datetime.now().isoformat()
            snippet['modified_by'] = CURRENT_USER

            # Save changes
            self.save_snippets()

            self.logger.debug(
                f"[2025-02-16 15:45:26] Snippet '{name}' statistics updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:45:26] Error updating snippet statistics: {str(e)}"
            )


    def setup_macro_recorder(self):
        """Setup macro recording functionality"""
        try:
            # Initialize macro system with typing
            self.macro_recording: bool = False
            self.current_macro: List[Dict] = []
            self.saved_macros: Dict[str, Dict] = {}

            # Load saved macros
            self.load_macros()

            # Setup macro toolbar with icons
            self.setup_macro_toolbar()

            self.logger.info(
                f"[2025-02-16 15:45:26] Macro recorder setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:45:26] Error setting up macro recorder: {str(e)}"
            )


    def load_macros(self):
        """
        Load saved macros from storage
        
        Last modified: 2025-02-16 15:46:06
        Modified by: vcutrone
        """
        try:
            macro_file = os.path.join(
                os.path.expanduser('~'),
                '.editor_macros.json'
            )

            if os.path.exists(macro_file):
                try:
                    with open(macro_file, 'r', encoding='utf-8') as f:
                        self.saved_macros = json.load(f)

                    # Validate loaded macros
                    self.validate_loaded_macros()

                except json.JSONDecodeError:
                    self.logger.error(
                        f"[2025-02-16 15:46:06] Invalid macro file format"
                    )
                    self.saved_macros = {}

            self.logger.debug(
                f"[2025-02-16 15:46:06] Macros loaded by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:46:06] Error loading macros: {str(e)}"
            )
            self.saved_macros = {}


    def validate_loaded_macros(self):
        """Validate loaded macros and remove invalid ones"""
        try:
            valid_macros = {}
            for name, macro in self.saved_macros.items():
                if self.is_valid_macro(name, macro):
                    valid_macros[name] = macro
                else:
                    self.logger.warning(
                        f"[2025-02-16 15:46:06] Invalid macro removed: {name}"
                    )

            self.saved_macros = valid_macros

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:46:06] Error validating macros: {str(e)}"
            )


    def is_valid_macro(self, name: str, macro: Dict) -> bool:
        """
        Check if a macro is valid
        
        Args:
            name (str): Macro name
            macro (Dict): Macro data
            
        Returns:
            bool: True if macro is valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = {'actions', 'created', 'modified'}
            if not all(field in macro for field in required_fields):
                return False

            # Check actions list
            if not isinstance(macro['actions'], list):
                return False

            # Validate each action
            for action in macro['actions']:
                if not isinstance(action, dict):
                    return False
                if 'type' not in action or 'data' not in action:
                    return False

            return True

        except Exception:
            return False


    def save_macros(self):
        """Save macros to storage with backup"""
        try:
            macro_file = os.path.join(
                os.path.expanduser('~'),
                '.editor_macros.json'
            )

            # Create backup if file exists
            if os.path.exists(macro_file):
                backup_file = f"{macro_file}.{int(time.time())}.bak"
                shutil.copy2(macro_file, backup_file)

            # Save with atomic write
            temp_file = f"{macro_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(
                    self.saved_macros,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

            os.replace(temp_file, macro_file)

            self.logger.debug(
                f"[2025-02-16 15:46:06] Macros saved by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:46:06] Error saving macros: {str(e)}"
            )


    def setup_macro_toolbar(self):
        """Setup macro recording toolbar with icons and shortcuts"""
        try:
            # Create macro toolbar
            self.macro_toolbar = QToolBar("Macros")
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.macro_toolbar)

            # Add record button with icon
            self.record_action = QAction(
                QIcon(":/icons/record.png"),
                "Record Macro",
                self
            )
            self.record_action.setCheckable(True)
            self.record_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
            self.record_action.setStatusTip("Start/Stop macro recording")
            self.record_action.triggered.connect(self.toggle_macro_recording)
            self.macro_toolbar.addAction(self.record_action)

            # Add save button
            self.save_macro_action = QAction(
                QIcon(":/icons/save.png"),
                "Save Macro",
                self
            )
            self.save_macro_action.setEnabled(False)
            self.save_macro_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
            self.save_macro_action.setStatusTip("Save recorded macro")
            self.save_macro_action.triggered.connect(self.show_save_macro_dialog)
            self.macro_toolbar.addAction(self.save_macro_action)

            # Add manage button
            manage_action = QAction(
                QIcon(":/icons/manage.png"),
                "Manage Macros",
                self
            )
            manage_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
            manage_action.setStatusTip("Manage saved macros")
            manage_action.triggered.connect(self.show_manage_macros_dialog)
            self.macro_toolbar.addAction(manage_action)

            self.logger.debug(
                f"[2025-02-16 15:46:06] Macro toolbar setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:46:06] Error setting up macro toolbar: {str(e)}"
            )


    def setup_code_completion(self):
        """
        Setup code completion system with language providers
        
        Last modified: 2025-02-16 15:48:31
        Modified by: vcutrone
        """
        try:
            # Initialize completion providers with proper typing
            self.completion_providers: Dict[str, CompletionProvider] = {
                'python': PythonCompletionProvider(self),
                'javascript': JavaScriptCompletionProvider(self),
                'typescript': TypeScriptCompletionProvider(self),
                'java': JavaCompletionProvider(self),
                'cpp': CppCompletionProvider(self),
                'go': GoCompletionProvider(self)
            }

            # Connect triggers
            self.connect_completion_triggers()

            # Initialize completion widget
            self.completion_widget = None

            self.logger.info(
                f"[2025-02-16 15:48:31] Code completion setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:48:31] Error setting up code completion: {str(e)}"
            )


    def connect_completion_triggers(self):
        """Connect code completion trigger events"""
        try:
            for editor in self.editors:
                # Disconnect existing signals to prevent duplicates
                try:
                    editor.textChanged.disconnect(self.handle_completion_trigger)
                    editor.cursorPositionChanged.disconnect(self.handle_completion_trigger)
                except:
                    pass

                # Connect signals
                editor.textChanged.connect(self.handle_completion_trigger)
                editor.cursorPositionChanged.connect(self.handle_completion_trigger)

            self.logger.debug(
                f"[2025-02-16 15:48:31] Completion triggers connected by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:48:31] Error connecting completion triggers: {str(e)}"
            )


    def handle_completion_trigger(self):
        """Handle code completion trigger event"""
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Get current language
            language = self.get_file_language(editor)
            if not language or language not in self.completion_providers:
                return

            # Get completion provider
            provider = self.completion_providers[language]

            # Get context
            cursor = editor.textCursor()
            block_text = cursor.block().text()
            position = cursor.positionInBlock()

            # Check trigger conditions
            if not self.should_trigger_completion(block_text, position):
                self.hide_completion_widget()
                return

            # Get suggestions
            suggestions = provider.get_completions(
                text=block_text,
                position=position,
                full_text=editor.toPlainText(),
                file_path=getattr(editor, 'file_path', None)
            )

            if suggestions:
                self.show_completion_popup(suggestions)
            else:
                self.hide_completion_widget()

            self.logger.debug(
                f"[2025-02-16 15:48:31] Handled completion trigger for {language}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:48:31] Error handling completion trigger: {str(e)}"
            )


    def should_trigger_completion(self, text: str, position: int) -> bool:
        """
        Check if completion should be triggered
        
        Args:
            text (str): Current line text
            position (int): Cursor position in line
            
        Returns:
            bool: True if completion should be triggered
        """
        try:
            if position == 0:
                return False

            # Get character before cursor
            prev_char = text[position - 1] if position > 0 else ''

            # Trigger conditions
            trigger_chars = {'.', ':', '(', '<', '"', "'"}

            # Check for identifier characters
            is_identifier = (
                    prev_char.isalnum() or
                    prev_char == '_'
            )

            # Check trigger conditions
            return (
                    prev_char in trigger_chars or
                    (is_identifier and position >= 3)
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:48:31] Error checking completion trigger: {str(e)}"
            )
            return False


    def show_completion_popup(self, suggestions: List[Dict]):
        """
        Show code completion popup with suggestions
        
        Args:
            suggestions (List[Dict]): List of completion suggestions
        
        Last modified: 2025-02-16 15:49:13
        Modified by: vcutrone
        """
        try:
            # Create or update completion widget
            if not self.completion_widget:
                self.completion_widget = CompletionWidget(self)
                self.completion_widget.item_selected.connect(
                    self.apply_completion
                )

            # Update suggestions
            self.completion_widget.update_suggestions(suggestions)

            # Position widget
            editor = self.current_editor()
            if not editor:
                return

            cursor = editor.textCursor()
            rect = editor.cursorRect(cursor)
            global_pos = editor.mapToGlobal(rect.bottomLeft())

            # Adjust position to avoid screen edges
            screen = QApplication.primaryScreen().geometry()
            widget_size = self.completion_widget.sizeHint()

            x = min(
                global_pos.x(),
                screen.right() - widget_size.width()
            )
            y = min(
                global_pos.y() + 5,
                screen.bottom() - widget_size.height()
            )

            self.completion_widget.move(x, y)
            self.completion_widget.show()

            self.logger.debug(
                f"[2025-02-16 15:49:13] Showed completion popup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:13] Error showing completion popup: {str(e)}"
            )


    def hide_completion_widget(self):
        """Hide code completion widget"""
        try:
            if self.completion_widget:
                self.completion_widget.hide()

            self.logger.debug(
                f"[2025-02-16 15:49:13] Hidden completion widget by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:13] Error hiding completion widget: {str(e)}"
            )


    def apply_completion(self, suggestion: Dict):
        """
        Apply selected completion suggestion
        
        Args:
            suggestion (Dict): Selected completion suggestion
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            cursor = editor.textCursor()

            # Start compound undo operation
            cursor.beginEditBlock()

            try:
                # Remove trigger text if needed
                if 'remove_chars' in suggestion:
                    for _ in range(suggestion['remove_chars']):
                        cursor.deletePreviousChar()

                # Insert completion text
                cursor.insertText(suggestion['text'])

                # Handle snippets with placeholders
                if 'snippet' in suggestion:
                    self.handle_snippet_placeholders(
                        suggestion['snippet'],
                        cursor
                    )

            finally:
                cursor.endEditBlock()

            # Hide completion widget
            self.hide_completion_widget()

            self.logger.debug(
                f"[2025-02-16 15:49:13] Applied completion by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:13] Error applying completion: {str(e)}"
            )


    def handle_snippet_placeholders(
            self,
            snippet: Dict,
            cursor: QTextCursor
    ):
        """
        Handle snippet placeholders after completion
        
        Args:
            snippet (Dict): Snippet information
            cursor (QTextCursor): Current text cursor
        """
        try:
            if 'placeholders' not in snippet:
                return

            # Store placeholder positions
            positions = []

            for placeholder in snippet['placeholders']:
                start = cursor.position() + placeholder['start']
                end = cursor.position() + placeholder['end']
                positions.append((start, end))

            # Select first placeholder if any
            if positions:
                cursor.setPosition(positions[0][0])
                cursor.setPosition(
                    positions[0][1],
                    QTextCursor.MoveMode.KeepAnchor
                )

            self.logger.debug(
                f"[2025-02-16 15:49:13] Handled snippet placeholders by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:13] Error handling snippet placeholders: {str(e)}"
            )


    def setup_code_analysis(self):
        """
        Setup code analysis system with language providers
        
        Last modified: 2025-02-16 15:49:53
        Modified by: vcutrone
        """
        try:
            # Initialize analysis providers with typing
            self.analysis_providers: Dict[str, AnalysisProvider] = {
                'python': PythonAnalysisProvider(self),
                'javascript': JavaScriptAnalysisProvider(self),
                'typescript': TypeScriptAnalysisProvider(self),
                'java': JavaAnalysisProvider(self),
                'cpp': CppAnalysisProvider(self),
                'go': GoAnalysisProvider(self)
            }

            # Setup analysis timer with debouncing
            self.analysis_delay = 1000  # 1 second delay
            self.analysis_timer = QTimer(self)
            self.analysis_timer.setSingleShot(True)
            self.analysis_timer.timeout.connect(self.run_code_analysis)

            # Connect editor signals
            self.connect_analysis_triggers()

            self.logger.info(
                f"[2025-02-16 15:49:53] Code analysis setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:53] Error setting up code analysis: {str(e)}"
            )


    def connect_analysis_triggers(self):
        """Connect code analysis trigger events"""
        try:
            for editor in self.editors:
                # Disconnect existing signals
                try:
                    editor.textChanged.disconnect(self.trigger_analysis)
                except:
                    pass

                # Connect signal
                editor.textChanged.connect(self.trigger_analysis)

            self.logger.debug(
                f"[2025-02-16 15:49:53] Analysis triggers connected by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:53] Error connecting analysis triggers: {str(e)}"
            )


    def trigger_analysis(self):
        """Trigger code analysis with debouncing"""
        try:
            # Reset timer
            self.analysis_timer.stop()
            self.analysis_timer.start(self.analysis_delay)

            self.logger.debug(
                f"[2025-02-16 15:49:53] Analysis triggered by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:53] Error triggering analysis: {str(e)}"
            )


    def run_code_analysis(self):
        """Run code analysis on current file"""
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Get current language
            language = self.get_file_language(editor)
            if not language or language not in self.analysis_providers:
                return

            # Get analysis provider
            provider = self.analysis_providers[language]

            # Get file content and path
            content = editor.toPlainText()
            file_path = getattr(editor, 'file_path', None)

            # Run analysis asynchronously
            self.run_analysis_async(
                provider,
                content,
                file_path
            )

            self.logger.debug(
                f"[2025-02-16 15:49:53] Running code analysis for {language}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:53] Error running code analysis: {str(e)}"
            )


    def run_analysis_async(
            self,
            provider: 'AnalysisProvider',
            content: str,
            file_path: Optional[str]
    ):
        """
        Run code analysis asynchronously
        
        Args:
            provider (AnalysisProvider): Analysis provider instance
            content (str): File content to analyze
            file_path (Optional[str]): Path to the file being analyzed
        """
        try:
            # Create analysis thread
            thread = QThread()
            worker = AnalysisWorker(
                provider,
                content,
                file_path
            )

            # Move worker to thread
            worker.moveToThread(thread)

            # Connect signals
            thread.started.connect(worker.run)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            worker.results_ready.connect(self.handle_analysis_results)

            # Start analysis
            thread.start()

            self.logger.debug(
                f"[2025-02-16 15:49:53] Started async analysis by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:49:53] Error running async analysis: {str(e)}"
            )


    def handle_analysis_results(self, results: List[Dict]):
        """
        Handle code analysis results
        
        Args:
            results (List[Dict]): Analysis results from provider
        
        Last modified: 2025-02-16 15:50:35
        Modified by: vcutrone
        """
        try:
            # Update editor markers
            self.update_analysis_markers(results)

            # Update status
            error_count = sum(1 for r in results if r['severity'] == 'error')
            warning_count = sum(1 for r in results if r['severity'] == 'warning')
            info_count = sum(1 for r in results if r['severity'] == 'info')

            self.update_analysis_status(
                error_count,
                warning_count,
                info_count
            )

            self.logger.debug(
                f"[2025-02-16 15:50:35] Handled analysis results by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:50:35] Error handling analysis results: {str(e)}"
            )


    def update_analysis_markers(self, results: List[Dict]):
        """
        Update code analysis markers in editor
        
        Args:
            results (List[Dict]): Analysis results to display
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Start performance benchmark
            start_time = time.time()

            # Clear existing markers
            editor.clear_analysis_markers()

            # Sort results by severity
            sorted_results = sorted(
                results,
                key=lambda x: {
                    'error': 0,
                    'warning': 1,
                    'info': 2
                }.get(x['severity'], 3)
            )

            # Add new markers
            for result in sorted_results:
                try:
                    # Extract marker information
                    line = result.get('line', 0)
                    column = result.get('column', 0)
                    length = result.get('length', 0)
                    severity = result.get('severity', 'info')
                    message = result.get('message', '')
                    code = result.get('code', '')

                    # Create marker
                    marker = AnalysisMarker(
                        line=line,
                        column=column,
                        length=length,
                        severity=severity,
                        message=message,
                        code=code
                    )

                    # Add to editor
                    editor.add_analysis_marker(marker)

                except Exception as e:
                    self.logger.error(
                        f"[2025-02-16 15:50:35] Error adding marker: {str(e)}"
                    )

            # Log performance
            elapsed = time.time() - start_time
            self.logger.debug(
                f"[2025-02-16 15:50:35] Updated {len(results)} markers in {elapsed:.3f}s"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:50:35] Error updating analysis markers: {str(e)}"
            )


    def update_analysis_status(
            self,
            errors: int,
            warnings: int,
            infos: int
    ):
        """
        Update analysis status in status bar
        
        Args:
            errors (int): Number of errors
            warnings (int): Number of warnings
            infos (int): Number of information messages
        """
        try:
            # Create status text
            parts = []
            if errors > 0:
                parts.append(f"{errors} error{'s' if errors != 1 else ''}")
            if warnings > 0:
                parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
            if infos > 0:
                parts.append(f"{infos} info message{'s' if infos != 1 else ''}")

            status_text = "Analysis: " + (
                ", ".join(parts) if parts else "No issues found"
            )

            # Create or update status label
            if not hasattr(self, 'analysis_status_label'):
                self.analysis_status_label = QLabel()
                self.statusBar().addPermanentWidget(self.analysis_status_label)

            self.analysis_status_label.setText(status_text)

            # Update label style
            if errors > 0:
                color = "#ff0000"  # Red
            elif warnings > 0:
                color = "#ffa500"  # Orange
            elif infos > 0:
                color = "#0000ff"  # Blue
            else:
                color = "#00aa00"  # Green

            self.analysis_status_label.setStyleSheet(
                f"color: {color}; font-weight: bold;"
            )

            self.logger.debug(
                f"[2025-02-16 15:50:35] Updated analysis status by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:50:35] Error updating analysis status: {str(e)}"
            )


    class AnalysisMarker:
        """Class representing a code analysis marker"""

        def __init__(
                self,
                line: int,
                column: int,
                length: int,
                severity: str,
                message: str,
                code: str
        ):
            self.line = line
            self.column = column
            self.length = length
            self.severity = severity
            self.message = message
            self.code = code

            # Set marker properties
            self.color = {
                'error': QColor("#ff0000"),
                'warning': QColor("#ffa500"),
                'info': QColor("#0000ff")
            }.get(severity, QColor("#000000"))

            self.style = {
                'error': Qt.PenStyle.SolidLine,
                'warning': Qt.PenStyle.DashLine,
                'info': Qt.PenStyle.DotLine
            }.get(severity, Qt.PenStyle.SolidLine)


    class AnalysisWorker(QObject):
        """
        Worker class for asynchronous code analysis
        
        Last modified: 2025-02-16 15:51:21
        Modified by: vcutrone
        """

        # Define signals
        results_ready = pyqtSignal(list)
        finished = pyqtSignal()

        def __init__(
                self,
                provider: 'AnalysisProvider',
                content: str,
                file_path: Optional[str]
        ):
            super().__init__()
            self.provider = provider
            self.content = content
            self.file_path = file_path
            self.logger = logging.getLogger(__name__)

        def run(self):
            """Run analysis in background thread"""
            try:
                # Run analysis
                results = self.provider.analyze_code(
                    self.content,
                    self.file_path
                )

                # Emit results
                self.results_ready.emit(results)

                self.logger.debug(
                    f"[2025-02-16 15:51:21] Analysis worker completed by {CURRENT_USER}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 15:51:21] Analysis worker error: {str(e)}"
                )
            finally:
                self.finished.emit()


    def setup_version_control(self):
        """Setup version control integration"""
        try:
            # Initialize VCS with typing
            self.vcs_provider: Optional['VCSProvider'] = None
            self.vcs_status: Dict[str, Dict] = {}

            # Try to detect VCS
            self.detect_vcs_provider()

            # Setup UI
            self.setup_vcs_toolbar()
            self.setup_vcs_status_bar()

            # Setup status polling with configurable interval
            self.vcs_poll_interval = 5000  # 5 seconds
            self.vcs_timer = QTimer(self)
            self.vcs_timer.timeout.connect(self.update_vcs_status)
            self.vcs_timer.start(self.vcs_poll_interval)

            self.logger.info(
                f"[2025-02-16 15:51:21] Version control setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:51:21] Error setting up version control: {str(e)}"
            )


    def detect_vcs_provider(self):
        """Detect and initialize VCS provider"""
        try:
            # Get project root
            root = self.get_project_root()
            if not root:
                return

            # Check for Git repository
            git_dir = os.path.join(root, '.git')
            if os.path.exists(git_dir):
                from .vcs.git import GitProvider
                self.vcs_provider = GitProvider(root)

            # Add support for other VCS here
            # elif os.path.exists(...):
            #     self.vcs_provider = OtherVCSProvider(root)

            if self.vcs_provider:
                self.logger.info(
                    f"[2025-02-16 15:51:21] Detected {type(self.vcs_provider).__name__}"
                )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:51:21] Error detecting VCS provider: {str(e)}"
            )


    def setup_vcs_toolbar(self):
        """Setup version control toolbar with icons and shortcuts"""
        try:
            # Create toolbar
            self.vcs_toolbar = QToolBar("Version Control")
            self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.vcs_toolbar)

            # Add commit action
            commit_action = QAction(
                QIcon(":/icons/commit.png"),
                "Commit Changes",
                self
            )
            commit_action.setShortcut("Ctrl+Alt+C")
            commit_action.setStatusTip("Commit staged changes")
            commit_action.triggered.connect(self.show_commit_dialog)
            self.vcs_toolbar.addAction(commit_action)

            # Add push action
            push_action = QAction(
                QIcon(":/icons/push.png"),
                "Push Changes",
                self
            )
            push_action.setShortcut("Ctrl+Alt+P")
            push_action.setStatusTip("Push commits to remote")
            push_action.triggered.connect(self.push_changes)
            self.vcs_toolbar.addAction(push_action)

            # Add pull action
            pull_action = QAction(
                QIcon(":/icons/pull.png"),
                "Pull Changes",
                self
            )
            pull_action.setShortcut("Ctrl+Alt+L")
            pull_action.setStatusTip("Pull changes from remote")
            pull_action.triggered.connect(self.pull_changes)
            self.vcs_toolbar.addAction(pull_action)

            self.vcs_toolbar.addSeparator()

            # Add branch action
            branch_action = QAction(
                QIcon(":/icons/branch.png"),
                "Manage Branches",
                self
            )
            branch_action.setShortcut("Ctrl+Alt+B")
            branch_action.setStatusTip("Manage branches")
            branch_action.triggered.connect(self.show_branch_dialog)
            self.vcs_toolbar.addAction(branch_action)

            # Add stage action
            stage_action = QAction(
                QIcon(":/icons/stage.png"),
                "Stage Changes",
                self
            )
            stage_action.setShortcut("Ctrl+Alt+S")
            stage_action.setStatusTip("Stage current file changes")
            stage_action.triggered.connect(self.stage_current_file)
            self.vcs_toolbar.addAction(stage_action)

            # Enable/disable based on VCS availability
            self.update_vcs_actions()

            self.logger.debug(
                f"[2025-02-16 15:51:21] VCS toolbar setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:51:21] Error setting up VCS toolbar: {str(e)}"
            )


    def setup_line_numbers(self):
        """
        Setup line numbers for all editors
        
        Last modified: 2025-02-16 15:53:24
        Modified by: vcutrone
        """
        try:
            # Configure line number area with proper typing
            for editor in self.editors:
                if not hasattr(editor, 'line_number_area'):
                    editor.line_number_area = LineNumberArea(editor)
                    editor.blockCountChanged.connect(editor.update_line_number_width)
                    editor.updateRequest.connect(editor.update_line_number_area)
                    editor.update_line_number_width()

            self.logger.debug(
                f"[2025-02-16 15:53:24] Line numbers setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:53:24] Error setting up line numbers: {str(e)}"
            )


    def update_line_numbers(self):
        """Update line numbers for current editor"""
        try:
            editor = self.current_editor()
            if not editor:
                return

            if hasattr(editor, 'line_number_area'):
                editor.update_line_number_width()
                editor.line_number_area.update()

            self.logger.debug(
                f"[2025-02-16 15:53:24] Line numbers updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:53:24] Error updating line numbers: {str(e)}"
            )


    class LineNumberArea(QWidget):
        """Widget for displaying line numbers"""

        def __init__(self, editor):
            super().__init__(editor)
            self.editor = editor
            self.setFont(editor.font())

        def sizeHint(self) -> QSize:
            return QSize(self.editor.line_number_area_width(), 0)

        def paintEvent(self, event: QPaintEvent):
            self.editor.paint_line_numbers(event)


    def setup_minimap(self):
        """Setup code minimap with customizable settings"""
        try:
            # Create minimap widget with configuration
            self.minimap = MinimapWidget(
                parent=self,
                font_size=self.settings.value('minimap/font_size', 1),
                opacity=self.settings.value('minimap/opacity', 0.7),
                show_current_line=self.settings.value('minimap/show_current_line', True)
            )

            # Add to dock widget with proper positioning
            minimap_dock = QDockWidget("Minimap", self)
            minimap_dock.setWidget(self.minimap)
            minimap_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, minimap_dock)

            # Connect signals
            self.tab_widget.currentChanged.connect(self.update_minimap)

            # Initial update
            self.update_minimap()

            self.logger.info(
                f"[2025-02-16 15:53:24] Minimap setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:53:24] Error setting up minimap: {str(e)}"
            )


    def update_minimap(self, index: int = None):
        """
        Update minimap with current editor content
        
        Args:
            index (int, optional): Tab index that changed
        """
        try:
            editor = self.current_editor()
            if not editor or not hasattr(self, 'minimap'):
                return

            # Update content with debouncing
            if hasattr(self, 'minimap_timer'):
                self.minimap_timer.stop()
            else:
                self.minimap_timer = QTimer(self)
                self.minimap_timer.setSingleShot(True)
                self.minimap_timer.timeout.connect(
                    lambda: self.minimap.update_content(editor)
                )

            self.minimap_timer.start(100)  # 100ms delay

            self.logger.debug(
                f"[2025-02-16 15:53:24] Minimap updated by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:53:24] Error updating minimap: {str(e)}"
            )


    def setup_code_folding(self):
        """
        Setup code folding functionality
        
        Last modified: 2025-02-16 15:54:01
        Modified by: vcutrone
        """
        try:
            # Configure folding for each editor
            for editor in self.editors:
                if not hasattr(editor, 'folding_manager'):
                    editor.folding_manager = CodeFoldingManager(editor)

                    # Connect signals
                    editor.blockCountChanged.connect(editor.folding_manager.update_folding_regions)
                    editor.textChanged.connect(editor.folding_manager.schedule_update)

                    # Setup folding margin
                    editor.setup_folding_margin()

            # Add folding actions to menu
            self.setup_folding_menu()

            self.logger.info(
                f"[2025-02-16 15:54:01] Code folding setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:01] Error setting up code folding: {str(e)}"
            )


    class CodeFoldingManager:
        """Manages code folding for an editor"""

        def __init__(self, editor):
            self.editor = editor
            self.folded_regions = {}
            self.update_timer = QTimer()
            self.update_timer.setSingleShot(True)
            self.update_timer.timeout.connect(self.update_folding_regions)

        def schedule_update(self):
            """Schedule delayed update of folding regions"""
            self.update_timer.start(500)  # 500ms delay

        def update_folding_regions(self):
            """Update folding regions in editor"""
            try:
                document = self.editor.document()
                self.folded_regions.clear()

                block = document.begin()
                while block.isValid():
                    if self.is_fold_start(block):
                        self.folded_regions[block.blockNumber()] = self.get_fold_range(block)
                    block = block.next()

                self.editor.update_folding_margin()

            except Exception as e:
                logger.error(
                    f"[2025-02-16 15:54:01] Error updating folding regions: {str(e)}"
                )


    def setup_folding_menu(self):
        """Setup code folding menu"""
        try:
            folding_menu = self.menuBar().addMenu("F&olding")

            actions = [
                ("Toggle Fold", "F9", self.toggle_fold),
                ("Toggle All Folds", "Shift+F9", self.toggle_all_folds),
                ("Fold All", "Ctrl+F9", self.fold_all),
                ("Unfold All", "Ctrl+Shift+F9", self.unfold_all)
            ]

            for name, shortcut, callback in actions:
                action = QAction(name, self)
                action.setShortcut(shortcut)
                action.triggered.connect(callback)
                folding_menu.addAction(action)

            self.logger.debug(
                f"[2025-02-16 15:54:01] Folding menu setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:01] Error setting up folding menu: {str(e)}"
            )


    def toggle_fold(self):
        """Toggle code fold at current position"""
        try:
            editor = self.current_editor()
            if not editor:
                return

            cursor = editor.textCursor()
            block = cursor.block()

            if editor.folding_manager.is_fold_start(block):
                if block.blockNumber() in editor.folding_manager.folded_regions:
                    self.unfold_block(editor, block)
                else:
                    self.fold_block(editor, block)

            self.logger.debug(
                f"[2025-02-16 15:54:01] Fold toggled by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:01] Error toggling fold: {str(e)}"
            )


    def toggle_all_folds(self):
        """Toggle all folds in editor"""
        try:
            editor = self.current_editor()
            if not editor:
                return

            if editor.folding_manager.folded_regions:
                self.unfold_all()
            else:
                self.fold_all()

            self.logger.debug(
                f"[2025-02-16 15:54:01] All folds toggled by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:01] Error toggling all folds: {str(e)}"
            )


    def fold_all(self):
        """
        Fold all foldable blocks in current editor
        
        Last modified: 2025-02-16 15:54:40
        Modified by: vcutrone
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Start compound undo operation
            cursor = editor.textCursor()
            cursor.beginEditBlock()

            try:
                # Process all blocks
                block = editor.document().begin()
                while block.isValid():
                    if (editor.folding_manager.is_fold_start(block) and
                            block.blockNumber() not in editor.folding_manager.folded_regions):
                        self.fold_block(editor, block)
                    block = block.next()

            finally:
                cursor.endEditBlock()

            self.logger.debug(
                f"[2025-02-16 15:54:40] All blocks folded by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:40] Error folding all blocks: {str(e)}"
            )


    def unfold_all(self):
        """Unfold all folded blocks in current editor"""
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Start compound undo operation
            cursor = editor.textCursor()
            cursor.beginEditBlock()

            try:
                # Process all folded blocks
                folded_blocks = list(editor.folding_manager.folded_regions.keys())
                for block_number in folded_blocks:
                    block = editor.document().findBlockByNumber(block_number)
                    if block.isValid():
                        self.unfold_block(editor, block)

            finally:
                cursor.endEditBlock()

            self.logger.debug(
                f"[2025-02-16 15:54:40] All blocks unfolded by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:40] Error unfolding all blocks: {str(e)}"
            )


    def fold_block(self, editor: QTextEdit, block: QTextBlock):
        """
        Fold a specific block in the editor
        
        Args:
            editor (QTextEdit): Editor instance
            block (QTextBlock): Block to fold
        """
        try:
            fold_range = editor.folding_manager.get_fold_range(block)
            if not fold_range:
                return

            start_line, end_line = fold_range

            # Store folded region
            editor.folding_manager.folded_regions[block.blockNumber()] = fold_range

            # Hide blocks in range
            current_block = block.next()
            while current_block.isValid() and current_block.blockNumber() <= end_line:
                editor.document().markContentsDirty(
                    current_block.position(),
                    current_block.length()
                )
                current_block.setVisible(False)
                current_block = current_block.next()

            # Update document layout
            editor.document().documentLayout().documentSizeChanged.emit()
            editor.update_folding_margin()

            self.logger.debug(
                f"[2025-02-16 15:54:40] Block {block.blockNumber()} folded by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:40] Error folding block: {str(e)}"
            )


    def unfold_block(self, editor: QTextEdit, block: QTextBlock):
        """
        Unfold a specific block in the editor
        
        Args:
            editor (QTextEdit): Editor instance
            block (QTextBlock): Block to unfold
        """
        try:
            if block.blockNumber() not in editor.folding_manager.folded_regions:
                return

            fold_range = editor.folding_manager.folded_regions.pop(block.blockNumber())
            start_line, end_line = fold_range

            # Show blocks in range
            current_block = block.next()
            while current_block.isValid() and current_block.blockNumber() <= end_line:
                current_block.setVisible(True)
                editor.document().markContentsDirty(
                    current_block.position(),
                    current_block.length()
                )
                current_block = current_block.next()

            # Update document layout
            editor.document().documentLayout().documentSizeChanged.emit()
            editor.update_folding_margin()

            self.logger.debug(
                f"[2025-02-16 15:54:40] Block {block.blockNumber()} unfolded by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:54:40] Error unfolding block: {str(e)}"
            )


    class FoldingMargin(QWidget):
        """Widget for displaying folding markers"""

        def __init__(self, editor):
            super().__init__(editor)
            self.editor = editor
            self.setFixedWidth(16)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        def paintEvent(self, event: QPaintEvent):
            try:
                painter = QPainter(self)
                painter.fillRect(event.rect(), self.palette().window())

                block = self.editor.firstVisibleBlock()
                while block.isValid():
                    y = self.editor.blockBoundingGeometry(block).translated(
                        self.editor.contentOffset()
                    ).top()

                    if y > event.rect().bottom():
                        break

                    if block.isVisible() and self.editor.folding_manager.is_fold_start(block):
                        is_folded = block.blockNumber() in self.editor.folding_manager.folded_regions
                        self.draw_fold_marker(painter, y, is_folded)

                    block = block.next()

            except Exception as e:
                logger.error(
                    f"[2025-02-16 15:54:40] Error painting folding margin: {str(e)}"
                )

        def draw_fold_marker(self, painter: QPainter, y: int, is_folded: bool):
            """Draw folding marker triangle"""
            try:
                rect = QRect(0, int(y), self.width(), self.editor.fontMetrics().height())
                painter.setPen(self.palette().text().color())

                # Draw triangle
                points = []
                if is_folded:
                    points = [
                        QPoint(6, rect.top() + 4),
                        QPoint(6, rect.bottom() - 4),
                        QPoint(10, rect.center().y())
                    ]
                else:
                    points = [
                        QPoint(4, rect.top() + 6),
                        QPoint(12, rect.top() + 6),
                        QPoint(8, rect.top() + 10)
                    ]

                painter.drawPolygon(QPolygon(points))

            except Exception as e:
                logger.error(
                    f"[2025-02-16 15:54:40] Error drawing fold marker: {str(e)}"
                )


    def setup_bookmarks(self):
        """
        Setup bookmarks functionality with enhanced features
        
        Last modified: 2025-02-16 15:55:27
        Modified by: vcutrone
        """
        try:
            # Initialize bookmarks with typing
            self.bookmarks: Dict[str, Set[int]] = {}
            self.current_bookmark: Optional[Tuple[str, int]] = None

            # Create bookmarks menu
            self.bookmarks_menu = QMenu("&Bookmarks", self)
            self.menuBar().addMenu(self.bookmarks_menu)

            # Add bookmark actions
            self.setup_bookmark_actions()

            # Add bookmark margin to editors
            for editor in self.editors:
                if not hasattr(editor, 'bookmark_margin'):
                    editor.bookmark_margin = BookmarkMargin(editor)

            self.logger.info(
                f"[2025-02-16 15:55:27] Bookmarks setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:55:27] Error setting up bookmarks: {str(e)}"
            )


    def setup_bookmark_actions(self):
        """Setup bookmark menu actions with shortcuts"""
        try:
            actions = [
                ("Toggle Bookmark", "Ctrl+F2", self.toggle_bookmark),
                ("Next Bookmark", "F2", self.goto_next_bookmark),
                ("Previous Bookmark", "Shift+F2", self.goto_previous_bookmark),
                ("Clear All Bookmarks", "Ctrl+Shift+F2", self.clear_bookmarks),
                (None, None, None),  # Separator
                ("Show All Bookmarks", "Alt+F2", self.show_bookmarks_dialog)
            ]

            for name, shortcut, callback in actions:
                if name is None:
                    self.bookmarks_menu.addSeparator()
                    continue

                action = QAction(name, self)
                if shortcut:
                    action.setShortcut(shortcut)
                action.triggered.connect(callback)
                self.bookmarks_menu.addAction(action)

            self.logger.debug(
                f"[2025-02-16 15:55:27] Bookmark actions setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:55:27] Error setting up bookmark actions: {str(e)}"
            )


    def toggle_bookmark(self):
        """Toggle bookmark at current line with persistence"""
        try:
            editor = self.current_editor()
            if not editor or not editor.file_path:
                return

            # Get current line
            cursor = editor.textCursor()
            line_number = cursor.blockNumber()

            # Toggle bookmark
            if self.is_line_bookmarked(editor.file_path, line_number):
                self.remove_bookmark(editor.file_path, line_number)
                self.show_status_message("Bookmark removed")
            else:
                self.add_bookmark(editor.file_path, line_number)
                self.show_status_message("Bookmark added")

            # Save bookmarks
            self.save_bookmarks()

            self.logger.debug(
                f"[2025-02-16 15:55:27] Bookmark toggled at line {line_number} by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:55:27] Error toggling bookmark: {str(e)}"
            )


    def is_line_bookmarked(self, file_path: str, line_number: int) -> bool:
        """
        Check if line is bookmarked
        
        Args:
            file_path (str): Path to the file
            line_number (int): Line number to check
            
        Returns:
            bool: True if line is bookmarked
        """
        try:
            return (
                    file_path in self.bookmarks and
                    line_number in self.bookmarks[file_path]
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:55:27] Error checking bookmark status: {str(e)}"
            )
            return False


    def add_bookmark(self, file_path: str, line_number: int):
        """
        Add bookmark at specified line
        
        Args:
            file_path (str): Path to the file
            line_number (int): Line number to bookmark
        """
        try:
            # Initialize file's bookmarks if needed
            if file_path not in self.bookmarks:
                self.bookmarks[file_path] = set()

            # Add bookmark
            self.bookmarks[file_path].add(line_number)

            # Update editor margin
            editor = self.get_editor_by_path(file_path)
            if editor and hasattr(editor, 'bookmark_margin'):
                editor.bookmark_margin.update()

            self.logger.debug(
                f"[2025-02-16 15:55:27] Bookmark added at line {line_number} by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:55:27] Error adding bookmark: {str(e)}"
            )


    def remove_bookmark(self, file_path: str, line_number: int):
        """
        Remove bookmark from specified line
        
        Args:
            file_path (str): Path to the file
            line_number (int): Line number to remove bookmark from
        """
        try:
            if file_path in self.bookmarks:
                # Remove bookmark
                self.bookmarks[file_path].discard(line_number)

                # Clean up if no bookmarks left
                if not self.bookmarks[file_path]:
                    del self.bookmarks[file_path]

                # Update editor margin
                editor = self.get_editor_by_path(file_path)
                if editor and hasattr(editor, 'bookmark_margin'):
                    editor.bookmark_margin.update()

                self.logger.debug(
                    f"[2025-02-16 15:55:27] Bookmark removed at line {line_number} by {CURRENT_USER}"
                )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:55:27] Error removing bookmark: {str(e)}"
            )


    def goto_next_bookmark(self):
        """
        Navigate to next bookmark in current or other files
        
        Last modified: 2025-02-16 15:56:09
        Modified by: vcutrone
        """
        try:
            editor = self.current_editor()
            if not editor or not editor.file_path:
                return

            current_line = editor.textCursor().blockNumber()

            # First try current file
            if editor.file_path in self.bookmarks:
                next_line = self.find_next_bookmark(
                    self.bookmarks[editor.file_path],
                    current_line
                )
                if next_line is not None:
                    self.goto_bookmark(editor.file_path, next_line)
                    return

            # Try other files if not found
            if len(self.bookmarks) > 1:
                next_file = self.find_next_bookmarked_file(editor.file_path)
                if next_file:
                    first_line = min(self.bookmarks[next_file])
                    self.goto_bookmark(next_file, first_line)

            self.logger.debug(
                f"[2025-02-16 15:56:09] Navigated to next bookmark by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:56:09] Error navigating to next bookmark: {str(e)}"
            )


    def find_next_bookmark(self, bookmarks: Set[int], current_line: int) -> Optional[int]:
        """
        Find next bookmark line number
        
        Args:
            bookmarks (Set[int]): Set of bookmarked lines
            current_line (int): Current line number
            
        Returns:
            Optional[int]: Next bookmark line or None
        """
        try:
            next_lines = [line for line in bookmarks if line > current_line]
            return min(next_lines) if next_lines else None

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:56:09] Error finding next bookmark: {str(e)}"
            )
            return None


    def goto_bookmark(self, file_path: str, line_number: int):
        """
        Navigate to specific bookmark
        
        Args:
            file_path (str): Path to the file
            line_number (int): Line number to navigate to
        """
        try:
            # Open file if needed
            editor = self.get_editor_by_path(file_path)
            if not editor:
                editor = self.open_file(file_path)

            if not editor:
                return

            # Navigate to line
            self.goto_line(editor, line_number)

            # Update current bookmark
            self.current_bookmark = (file_path, line_number)

            self.logger.debug(
                f"[2025-02-16 15:56:09] Navigated to bookmark at line {line_number} by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:56:09] Error navigating to bookmark: {str(e)}"
            )


    def save_bookmarks(self):
        """Save bookmarks to settings"""
        try:
            # Convert bookmarks to serializable format
            bookmark_data = {
                path: list(lines)
                for path, lines in self.bookmarks.items()
            }

            # Save to settings
            self.settings.setValue('bookmarks', bookmark_data)

            self.logger.debug(
                f"[2025-02-16 15:56:09] Bookmarks saved by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:56:09] Error saving bookmarks: {str(e)}"
            )


    def load_bookmarks(self):
        """Load bookmarks from settings"""
        try:
            # Load from settings
            bookmark_data = self.settings.value('bookmarks', {})

            # Convert to internal format
            self.bookmarks = {
                path: set(lines)
                for path, lines in bookmark_data.items()
                if os.path.exists(path)  # Only load if file exists
            }

            # Update editors
            for editor in self.editors:
                if hasattr(editor, 'bookmark_margin'):
                    editor.bookmark_margin.update()

            self.logger.debug(
                f"[2025-02-16 15:56:09] Bookmarks loaded by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:56:09] Error loading bookmarks: {str(e)}"
            )


    class BookmarkMargin(QWidget):
        """Widget for displaying bookmark markers"""

        def __init__(self, editor):
            super().__init__(editor)
            self.editor = editor
            self.setFixedWidth(16)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        def paintEvent(self, event: QPaintEvent):
            try:
                painter = QPainter(self)
                painter.fillRect(event.rect(), self.palette().window())

                if not self.editor.file_path:
                    return

                # Draw bookmark markers
                block = self.editor.firstVisibleBlock()
                while block.isValid():
                    y = self.editor.blockBoundingGeometry(block).translated(
                        self.editor.contentOffset()
                    ).top()

                    if y > event.rect().bottom():
                        break

                    if block.isVisible() and self.is_line_bookmarked(block.blockNumber()):
                        self.draw_bookmark_marker(painter, y)

                    block = block.next()

            except Exception as e:
                logger.error(
                    f"[2025-02-16 15:56:09] Error painting bookmark margin: {str(e)}"
                )

        def is_line_bookmarked(self, line_number: int) -> bool:
            """Check if line has bookmark"""
            try:
                window = self.window()
                return window.is_line_bookmarked(
                    self.editor.file_path,
                    line_number
                )

            except Exception:
                return False

        def draw_bookmark_marker(self, painter: QPainter, y: int):
            """Draw bookmark marker icon"""
            try:
                height = self.editor.fontMetrics().height()

                # Draw bookmark symbol
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#4B9EFA"))

                painter.drawRect(
                    4,
                    int(y) + 2,
                    8,
                    height - 4
                )

            except Exception as e:
                logger.error(
                    f"[2025-02-16 15:56:09] Error drawing bookmark marker: {str(e)}"
                )


    def show_bookmarks_dialog(self):
        """Show dialog with all bookmarks"""
        try:
            dialog = BookmarksDialog(self.bookmarks, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected = dialog.get_selected_bookmark()
                if selected:
                    file_path, line_number = selected
                    self.goto_bookmark(file_path, line_number)

            self.logger.debug(
                f"[2025-02-16 15:56:09] Showed bookmarks dialog by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:56:09] Error showing bookmarks dialog: {str(e)}"
            )


    def next_bookmark(self):
        """
        Navigate to next bookmark with enhanced navigation
        
        Last modified: 2025-02-16 15:58:50
        Modified by: vcutrone
        """
        try:
            editor = self.current_editor()
            if not editor or not editor.file_path:
                return False

            # Get current bookmarks for file
            bookmarks = self.bookmarks.get(editor.file_path, set())
            if not bookmarks:
                self.show_status_message("No bookmarks in current file")
                return False

            # Get current line
            current_line = editor.textCursor().blockNumber()

            # Find next bookmark
            next_line = None
            for line in sorted(bookmarks):
                if line > current_line:
                    next_line = line
                    break

            # Wrap around if needed
            if next_line is None:
                next_line = min(bookmarks)

            # Navigate to bookmark
            self.goto_line(editor, next_line)
            self.show_status_message(f"Moved to bookmark at line {next_line + 1}")

            self.logger.debug(
                f"[2025-02-16 15:58:50] Navigated to next bookmark by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:58:50] Error navigating to next bookmark: {str(e)}"
            )
            return False


    def previous_bookmark(self):
        """Navigate to previous bookmark with enhanced navigation"""
        try:
            editor = self.current_editor()
            if not editor or not editor.file_path:
                return False

            # Get current bookmarks for file
            bookmarks = self.bookmarks.get(editor.file_path, set())
            if not bookmarks:
                self.show_status_message("No bookmarks in current file")
                return False

            # Get current line
            current_line = editor.textCursor().blockNumber()

            # Find previous bookmark
            prev_line = None
            for line in sorted(bookmarks, reverse=True):
                if line < current_line:
                    prev_line = line
                    break

            # Wrap around if needed
            if prev_line is None:
                prev_line = max(bookmarks)

            # Navigate to bookmark
            self.goto_line(editor, prev_line)
            self.show_status_message(f"Moved to bookmark at line {prev_line + 1}")

            self.logger.debug(
                f"[2025-02-16 15:58:50] Navigated to previous bookmark by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:58:50] Error navigating to previous bookmark: {str(e)}"
            )
            return False


    def goto_line(self, editor: QTextEdit, line_number: int):
        """
        Go to specified line in editor with proper positioning
        
        Args:
            editor (QTextEdit): Editor widget
            line_number (int): Line number to navigate to
        """
        try:
            # Create cursor at target line
            block = editor.document().findBlockByNumber(line_number)
            if not block.isValid():
                return False

            cursor = QTextCursor(block)
            editor.setTextCursor(cursor)

            # Ensure line is visible with context
            editor.centerCursor()
            editor.setFocus()

            # Highlight line temporarily
            self.highlight_current_line(editor)

            self.logger.debug(
                f"[2025-02-16 15:58:50] Navigated to line {line_number} by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:58:50] Error navigating to line: {str(e)}"
            )
            return False


    def highlight_current_line(self, editor: QTextEdit):
        """
        Temporarily highlight current line for visibility
        
        Args:
            editor (QTextEdit): Editor widget
        """
        try:
            # Save original colors
            original_bg = editor.palette().color(QPalette.ColorRole.Base)

            # Create highlight animation
            highlight_color = QColor("#FFE2BC")
            animation = QPropertyAnimation(editor, b"palette")
            animation.setDuration(1000)  # 1 second

            # Setup keyframes
            start_palette = editor.palette()
            end_palette = QPalette(start_palette)

            highlight_palette = QPalette(start_palette)
            highlight_palette.setColor(QPalette.ColorRole.Base, highlight_color)

            animation.setStartValue(start_palette)
            animation.setKeyValueAt(0.2, highlight_palette)
            animation.setEndValue(end_palette)

            # Start animation
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:58:50] Error highlighting line: {str(e)}"
            )


    def setup_code_folding(self):
        """
        Setup code folding functionality with advanced features
        
        Last modified: 2025-02-16 15:59:31
        Modified by: vcutrone
        """
        try:
            # Add code folding actions to View menu
            self.folding_menu = self.view_menu.addMenu("Code &Folding")

            folding_actions = [
                ("Toggle Fold", "Ctrl+Shift+[", self.toggle_fold),
                ("Fold All", "Ctrl+Alt+[", self.fold_all),
                ("Unfold All", "Ctrl+Alt+]", self.unfold_all),
                (None, None, None),  # Separator
                ("Fold Level 1", "Alt+1", lambda: self.fold_level(1)),
                ("Fold Level 2", "Alt+2", lambda: self.fold_level(2)),
                ("Fold Level 3", "Alt+3", lambda: self.fold_level(3))
            ]

            for name, shortcut, callback in folding_actions:
                if name is None:
                    self.folding_menu.addSeparator()
                    continue

                action = QAction(name, self)
                if shortcut:
                    action.setShortcut(shortcut)
                action.triggered.connect(callback)
                self.folding_menu.addAction(action)

            # Initialize folding managers for editors
            for editor in self.editors:
                if not hasattr(editor, 'folding_manager'):
                    editor.folding_manager = CodeFoldingManager(editor)

            self.logger.info(
                f"[2025-02-16 15:59:31] Code folding setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 15:59:31] Error setting up code folding: {str(e)}"
            )


    class CodeFoldingManager:
        """Manages code folding for an editor"""

        def __init__(self, editor: QTextEdit):
            self.editor = editor
            self.folded_regions: Dict[int, Tuple[int, int]] = {}
            self.fold_indicators: Dict[int, QWidget] = {}

            # Setup delayed update
            self.update_timer = QTimer()
            self.update_timer.setSingleShot(True)
            self.update_timer.timeout.connect(self.update_fold_regions)

            # Connect to editor signals
            self.editor.textChanged.connect(self.schedule_update)
            self.editor.blockCountChanged.connect(self.schedule_update)

        def schedule_update(self):
            """Schedule delayed update of fold regions"""
            self.update_timer.start(500)  # 500ms delay

        def update_fold_regions(self):
            """Update folding regions based on code structure"""
            try:
                document = self.editor.document()
                block = document.begin()

                # Clear existing regions
                old_regions = self.folded_regions.copy()
                self.folded_regions.clear()

                # Find new folding regions
                while block.isValid():
                    if self.is_fold_start(block):
                        end_line = self.find_fold_end(block)
                        if end_line > block.blockNumber():
                            self.folded_regions[block.blockNumber()] = (
                                block.blockNumber(),
                                end_line
                            )

                    block = block.next()

                # Restore previously folded state
                for start_line in old_regions:
                    if start_line in self.folded_regions:
                        self.fold_block(start_line)

                # Update UI
                self.update_fold_indicators()

            except Exception as e:
                logger.error(
                    f"[2025-02-16 15:59:31] Error updating fold regions: {str(e)}"
                )

        def is_fold_start(self, block: QTextBlock) -> bool:
            """
            Check if block is a fold start point
            
            Args:
                block (QTextBlock): Block to check
                
            Returns:
                bool: True if block can start a fold
            """
            try:
                text = block.text().strip()

                # Check for common fold start patterns
                patterns = [
                    r'^\s*(?:class|def)\s+\w+.*:$',  # Python class/function
                    r'^\s*(?:if|for|while|try)\s*.*:$',  # Python control structures
                    r'^\s*{\s*$',  # Curly brace languages
                    r'^\s*//\s*region\b',  # C# region
                    r'^\s*/\*',  # Multi-line comment start
                    r'^\s*<!--'  # HTML comment start
                ]

                return any(re.match(pattern, text) for pattern in patterns)

            except Exception as e:
                logger.error(
                    f"[2025-02-16 15:59:31] Error checking fold start: {str(e)}"
                )
                return False


    def find_fold_end(self, block: QTextBlock) -> int:
        """
        Find the end line of a fold region
        
        Last modified: 2025-02-16 16:00:23
        Modified by: vcutrone
        
        Args:
            block (QTextBlock): Starting block of fold
            
        Returns:
            int: Line number of fold end
        """
        try:
            start_indent = self.get_block_indent(block)
            current_block = block.next()

            while current_block.isValid():
                # Check indentation level
                current_indent = self.get_block_indent(current_block)

                # Empty lines don't break the fold
                if not current_block.text().strip():
                    current_block = current_block.next()
                    continue

                # End fold when finding same or lower indentation
                if current_indent <= start_indent:
                    return current_block.blockNumber() - 1

                current_block = current_block.next()

            # If we reach the end, use last line
            return self.editor.document().lineCount() - 1

        except Exception as e:
            logger.error(
                f"[2025-02-16 16:00:23] Error finding fold end: {str(e)}"
            )
            return block.blockNumber()


    def get_block_indent(self, block: QTextBlock) -> int:
        """
        Get indentation level of a block
        
        Args:
            block (QTextBlock): Block to check
            
        Returns:
            int: Number of spaces/tabs at start
        """
        try:
            text = block.text()
            indent = len(text) - len(text.lstrip())
            return indent

        except Exception as e:
            logger.error(
                f"[2025-02-16 16:00:23] Error getting block indent: {str(e)}"
            )
            return 0


    def fold_block(self, line_number: int) -> bool:
        """
        Fold a specific block
        
        Args:
            line_number (int): Line number to fold
            
        Returns:
            bool: True if fold successful
        """
        try:
            if line_number not in self.folded_regions:
                return False

            start_line, end_line = self.folded_regions[line_number]

            # Hide blocks in fold region
            block = self.editor.document().findBlockByNumber(start_line + 1)
            while block.isValid() and block.blockNumber() <= end_line:
                block.setVisible(False)
                block = block.next()

            # Update document layout
            self.editor.document().markContentsDirty(
                block.position(),
                block.length()
            )

            # Update UI
            self.update_fold_indicators()

            self.logger.debug(
                f"[2025-02-16 16:00:23] Folded block at line {line_number} by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:00:23] Error folding block: {str(e)}"
            )
            return False


    def unfold_block(self, line_number: int) -> bool:
        """
        Unfold a specific block
        
        Args:
            line_number (int): Line number to unfold
            
        Returns:
            bool: True if unfold successful
        """
        try:
            if line_number not in self.folded_regions:
                return False

            start_line, end_line = self.folded_regions[line_number]

            # Show blocks in fold region
            block = self.editor.document().findBlockByNumber(start_line + 1)
            while block.isValid() and block.blockNumber() <= end_line:
                block.setVisible(True)
                block = block.next()

            # Update document layout
            self.editor.document().markContentsDirty(
                block.position(),
                block.length()
            )

            # Update UI
            self.update_fold_indicators()

            self.logger.debug(
                f"[2025-02-16 16:00:23] Unfolded block at line {line_number} by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:00:23] Error unfolding block: {str(e)}"
            )
            return False


    def update_fold_indicators(self):
        """Update fold indicators in the margin"""
        try:
            # Remove old indicators
            for indicator in self.fold_indicators.values():
                indicator.deleteLater()
            self.fold_indicators.clear()

            # Create new indicators
            for line_number in self.folded_regions:
                indicator = FoldIndicator(
                    self.editor,
                    line_number,
                    self.is_block_folded(line_number)
                )
                self.fold_indicators[line_number] = indicator

            self.logger.debug(
                f"[2025-02-16 16:00:23] Updated fold indicators by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:00:23] Error updating fold indicators: {str(e)}"
            )


    def is_block_folded(self, line_number: int) -> bool:
        """
        Check if a block is currently folded
        
        Args:
            line_number (int): Line number to check
            
        Returns:
            bool: True if block is folded
        """
        try:
            if line_number not in self.folded_regions:
                return False

            start_line, _ = self.folded_regions[line_number]
            block = self.editor.document().findBlockByNumber(start_line + 1)
            return not block.isVisible()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:00:23] Error checking block fold status: {str(e)}"
            )
            return False


    class FoldIndicator(QWidget):
        """
        Widget for displaying fold indicators in the margin
        
        Last modified: 2025-02-16 16:01:07
        Modified by: vcutrone
        """

        def __init__(self, editor: QTextEdit, line_number: int, is_folded: bool):
            super().__init__(editor)
            self.editor = editor
            self.line_number = line_number
            self.is_folded = is_folded

            # Configure appearance
            self.setFixedSize(16, 16)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            # Position indicator
            self.update_position()

            # Show widget
            self.show()

            # Connect signals
            self.editor.updateRequest.connect(self.update_position)

        def update_position(self):
            """Update indicator position based on line position"""
            try:
                block = self.editor.document().findBlockByNumber(self.line_number)
                if not block.isValid():
                    self.hide()
                    return

                # Calculate position
                viewport = self.editor.viewport()
                offset = self.editor.contentOffset()
                pos = self.editor.blockBoundingGeometry(block).translated(offset).topLeft()

                # Position in margin
                margin_width = self.editor.fontMetrics().horizontalAdvance('9') * 4
                self.move(viewport.x() - margin_width, int(pos.y()))

            except Exception as e:
                logger.error(
                    f"[2025-02-16 16:01:07] Error updating fold indicator position: {str(e)}"
                )

        def paintEvent(self, event: QPaintEvent):
            """Draw the fold indicator triangle"""
            try:
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Configure painter
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#666666"))

                # Calculate triangle points
                rect = self.rect()
                if self.is_folded:
                    points = [
                        QPoint(rect.left() + 4, rect.top() + 4),
                        QPoint(rect.right() - 4, rect.top() + 8),
                        QPoint(rect.left() + 4, rect.bottom() - 4)
                    ]
                else:
                    points = [
                        QPoint(rect.left() + 4, rect.top() + 4),
                        QPoint(rect.right() - 4, rect.top() + 4),
                        QPoint(rect.left() + 8, rect.bottom() - 4)
                    ]

                # Draw triangle
                painter.drawPolygon(QPolygon(points))

            except Exception as e:
                logger.error(
                    f"[2025-02-16 16:01:07] Error painting fold indicator: {str(e)}"
                )

        def mousePressEvent(self, event: QMouseEvent):
            """Handle click to toggle fold"""
            try:
                if event.button() == Qt.MouseButton.LeftButton:
                    if self.is_folded:
                        self.editor.folding_manager.unfold_block(self.line_number)
                    else:
                        self.editor.folding_manager.fold_block(self.line_number)

            except Exception as e:
                logger.error(
                    f"[2025-02-16 16:01:07] Error handling fold indicator click: {str(e)}"
                )


    def toggle_fold(self):
        """Toggle fold at cursor position"""
        try:
            editor = self.current_editor()
            if not editor:
                return False

            cursor = editor.textCursor()
            block = cursor.block()
            line_number = block.blockNumber()

            if not editor.folding_manager.is_fold_start(block):
                self.show_status_message("No fold point at cursor")
                return False

            if editor.folding_manager.is_block_folded(line_number):
                success = editor.folding_manager.unfold_block(line_number)
                if success:
                    self.show_status_message("Fold expanded")
            else:
                success = editor.folding_manager.fold_block(line_number)
                if success:
                    self.show_status_message("Fold collapsed")

            self.logger.debug(
                f"[2025-02-16 16:01:07] Toggled fold at line {line_number} by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:07] Error toggling fold: {str(e)}"
            )
            return False


    def fold_level(self, level: int):
        """
        Fold all blocks at specified indent level
        
        Args:
            level (int): Indentation level to fold
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Start compound undo operation
            cursor = editor.textCursor()
            cursor.beginEditBlock()

            try:
                block = editor.document().begin()
                folded_count = 0

                while block.isValid():
                    if (editor.folding_manager.is_fold_start(block) and
                            editor.folding_manager.get_block_indent(block) == level * 4):
                        if editor.folding_manager.fold_block(block.blockNumber()):
                            folded_count += 1
                    block = block.next()

                self.show_status_message(f"Folded {folded_count} blocks at level {level}")

            finally:
                cursor.endEditBlock()

            self.logger.debug(
                f"[2025-02-16 16:01:07] Folded level {level} by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:07] Error folding level {level}: {str(e)}"
            )


    def fold_all(self):
        """
        Fold all possible blocks in current editor
        
        Last modified: 2025-02-16 16:01:53
        Modified by: vcutrone
        """
        try:
            editor = self.current_editor()
            if not editor:
                return False

            # Start compound undo operation
            cursor = editor.textCursor()
            cursor.beginEditBlock()

            try:
                block = editor.document().begin()
                folded_count = 0

                while block.isValid():
                    if editor.folding_manager.is_fold_start(block):
                        if editor.folding_manager.fold_block(block.blockNumber()):
                            folded_count += 1
                    block = block.next()

                self.show_status_message(f"Folded {folded_count} blocks")

            finally:
                cursor.endEditBlock()

            self.logger.debug(
                f"[2025-02-16 16:01:53] Folded all blocks ({folded_count}) by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:53] Error folding all blocks: {str(e)}"
            )
            return False


    def unfold_all(self):
        """Unfold all folded blocks in current editor"""
        try:
            editor = self.current_editor()
            if not editor:
                return False

            # Start compound undo operation
            cursor = editor.textCursor()
            cursor.beginEditBlock()

            try:
                folded_regions = list(editor.folding_manager.folded_regions.keys())
                unfolded_count = 0

                for line_number in folded_regions:
                    if editor.folding_manager.unfold_block(line_number):
                        unfolded_count += 1

                self.show_status_message(f"Unfolded {unfolded_count} blocks")

            finally:
                cursor.endEditBlock()

            self.logger.debug(
                f"[2025-02-16 16:01:53] Unfolded all blocks ({unfolded_count}) by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:53] Error unfolding all blocks: {str(e)}"
            )
            return False


    def setup_minimap(self):
        """Setup code minimap with enhanced features"""
        try:
            # Create minimap widget with configuration
            self.minimap = MinimapWidget(
                parent=self,
                font_size=self.settings.value('minimap/font_size', 1),
                opacity=self.settings.value('minimap/opacity', 0.7),
                show_current_line=self.settings.value('minimap/show_current_line', True),
                show_scrollbar=self.settings.value('minimap/show_scrollbar', True)
            )

            # Create minimap dock widget
            self.minimap_dock = QDockWidget("Minimap", self)
            self.minimap_dock.setWidget(self.minimap)
            self.minimap_dock.setAllowedAreas(
                Qt.DockWidgetArea.RightDockWidgetArea |
                Qt.DockWidgetArea.LeftDockWidgetArea
            )

            # Add dock widget
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock)

            # Setup update timer
            self.minimap_update_timer = QTimer(self)
            self.minimap_update_timer.setSingleShot(True)
            self.minimap_update_timer.timeout.connect(self.update_minimap)

            # Connect signals
            self.tab_widget.currentChanged.connect(self.schedule_minimap_update)

            self.logger.info(
                f"[2025-02-16 16:01:53] Minimap setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:53] Error setting up minimap: {str(e)}"
            )


    def schedule_minimap_update(self):
        """Schedule delayed minimap update"""
        try:
            self.minimap_update_timer.start(100)  # 100ms delay

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:53] Error scheduling minimap update: {str(e)}"
            )


    def update_minimap(self):
        """Update minimap with current editor content"""
        try:
            editor = self.current_editor()
            if not editor:
                self.minimap.clear()
                return False

            # Get visible content
            viewport = editor.viewport()
            visible_rect = editor.viewport().rect()
            visible_rect.translate(0, editor.verticalScrollBar().value())

            # Update minimap
            self.minimap.set_content(
                text=editor.toPlainText(),
                current_line=editor.textCursor().blockNumber(),
                visible_range=(
                    editor.firstVisibleBlock().blockNumber(),
                    editor.blockCount()
                ),
                highlights=self.get_minimap_highlights(editor)
            )

            self.logger.debug(
                f"[2025-02-16 16:01:53] Updated minimap by {CURRENT_USER}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:53] Error updating minimap: {str(e)}"
            )
            return False


    def get_minimap_highlights(self, editor: QTextEdit) -> List[Tuple[int, str]]:
        """
        Get list of highlighted lines for minimap
        
        Args:
            editor (QTextEdit): Current editor
            
        Returns:
            List[Tuple[int, str]]: List of (line_number, color) pairs
        """
        try:
            highlights = []

            # Add current line
            cursor = editor.textCursor()
            highlights.append((cursor.blockNumber(), "#FFE2BC"))

            # Add search results
            if hasattr(editor, 'search_highlights'):
                for line in editor.search_highlights:
                    highlights.append((line, "#B3E5FC"))

            # Add error/warning markers
            if hasattr(editor, 'error_markers'):
                for line, severity in editor.error_markers.items():
                    color = "#FFCDD2" if severity == 'error' else "#FFF9C4"
                    highlights.append((line, color))

            return highlights

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:01:53] Error getting minimap highlights: {str(e)}"
            )
            return []


    def run_code_analysis(self) -> bool:
        """
        Run code analysis on current file with enhanced error checking
        
        Last modified: 2025-02-16 16:04:15
        Modified by: vcutrone
        
        Returns:
            bool: True if analysis started successfully
        """
        try:
            editor = self.current_editor()
            if not editor:
                self.show_status_message("No active editor")
                return False

            file_path = editor.file_path
            if not file_path:
                self.show_status_message("Save file before analysis")
                return False

            # Show analysis panel
            self.analysis_dock.show()
            self.analysis_dock.raise_()

            # Get file extension
            extension = os.path.splitext(file_path)[1].lower()

            # Start analysis with progress indicator
            if self.code_analysis.start_analysis(file_path, extension):
                self.show_progress_message(
                    f"Analyzing {os.path.basename(file_path)}..."
                )
                self.logger.debug(
                    f"[2025-02-16 16:04:15] Started code analysis by {CURRENT_USER}"
                )
                return True

            self.show_status_message("Unsupported file type for analysis")
            return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:04:15] Error running code analysis: {str(e)}"
            )
            self.show_status_message("Analysis failed", error=True)
            return False


    def on_analysis_complete(self, results: List[Dict[str, Any]]):
        """
        Handle completion of code analysis
        
        Args:
            results: List of analysis results, each containing:
                - severity: str ('error', 'warning', 'info')
                - line: int
                - message: str
                - code: str (optional)
                - source: str (optional)
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Clear previous markers
            editor.clear_analysis_markers()

            # Process results
            error_count = 0
            warning_count = 0
            info_count = 0

            for result in results:
                severity = result.get('severity', 'info')
                line = result.get('line', 0)
                message = result.get('message', '')
                code = result.get('code', '')
                source = result.get('source', '')

                # Add marker with tooltip
                tooltip = f"{severity.upper()}: {message}"
                if code:
                    tooltip += f"\nCode: {code}"
                if source:
                    tooltip += f"\nSource: {source}"

                if severity == 'error':
                    editor.add_error_marker(line, tooltip)
                    error_count += 1
                elif severity == 'warning':
                    editor.add_warning_marker(line, tooltip)
                    warning_count += 1
                else:
                    editor.add_info_marker(line, tooltip)
                    info_count += 1

            # Update status
            status = f"Analysis complete: "
            if error_count > 0:
                status += f"{error_count} error(s), "
            if warning_count > 0:
                status += f"{warning_count} warning(s), "
            if info_count > 0:
                status += f"{info_count} info(s)"

            self.show_status_message(status.rstrip(", "))

            self.logger.debug(
                f"[2025-02-16 16:04:15] Completed code analysis by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:04:15] Error handling analysis completion: {str(e)}"
            )
            self.show_status_message("Error processing analysis results", error=True)


    def setup_code_completion(self):
        """
        Setup code completion with enhanced features
        
        Last modified: 2025-02-16 16:04:56
        Modified by: vcutrone
        """
        try:
            # Initialize completer with configuration
            self.completer = CodeCompleter(
                parent=self,
                case_sensitive=self.settings.value('completion/case_sensitive', False),
                trigger_length=self.settings.value('completion/trigger_length', 2),
                auto_trigger=self.settings.value('completion/auto_trigger', True),
                show_icons=self.settings.value('completion/show_icons', True)
            )

            # Setup completion widgets
            self.completion_list = CompletionListWidget(self)
            self.completion_info = CompletionInfoWidget(self)

            # Configure list appearance
            self.completion_list.setMaximumHeight(200)
            self.completion_list.setMinimumWidth(300)
            self.completion_list.hide()

            # Configure info widget
            self.completion_info.setMaximumWidth(400)
            self.completion_info.hide()

            # Connect signals for editors
            for editor in self.editors:
                self.connect_completion_signals(editor)

            self.logger.info(
                f"[2025-02-16 16:04:56] Code completion setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:04:56] Error setting up code completion: {str(e)}"
            )


    def connect_completion_signals(self, editor: QTextEdit):
        """
        Connect code completion signals for an editor
        
        Args:
            editor (QTextEdit): Editor to connect signals for
        """
        try:
            # Text change signals
            editor.textChanged.connect(
                lambda: self.handle_text_changed(editor)
            )

            # Key press signals
            editor.keyPressEvent = self.wrap_key_press_event(
                editor,
                editor.keyPressEvent
            )

            # Focus signals
            editor.focusOutEvent = self.wrap_focus_out_event(
                editor,
                editor.focusOutEvent
            )

            self.logger.debug(
                f"[2025-02-16 16:04:56] Connected completion signals by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:04:56] Error connecting completion signals: {str(e)}"
            )


    def handle_text_changed(self, editor: QTextEdit):
        """
        Handle text changes for code completion
        
        Args:
            editor (QTextEdit): Editor that changed
        """
        try:
            if not self.completer.auto_trigger:
                return

            # Get current context
            cursor = editor.textCursor()
            text = cursor.block().text()
            position = cursor.positionInBlock()

            # Check trigger conditions
            if position < self.completer.trigger_length:
                self.hide_completion()
                return

            # Get trigger text
            trigger_text = text[position - self.completer.trigger_length:position]

            # Check if completion should be triggered
            if self.should_trigger_completion(trigger_text):
                self.request_completions(editor)

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:04:56] Error handling text change: {str(e)}"
            )


    def should_trigger_completion(self, text: str) -> bool:
        """
        Check if completion should be triggered
        
        Args:
            text (str): Text to check
            
        Returns:
            bool: True if completion should be triggered
        """
        try:
            # Don't trigger on whitespace
            if text.isspace():
                return False

            # Check for trigger characters
            trigger_chars = set('.', '_', ':', '>')
            if any(char in text for char in trigger_chars):
                return True

            # Check for word characters
            return text.isalnum()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:04:56] Error checking completion trigger: {str(e)}"
            )
            return False


    def request_completions(self, editor: QTextEdit):
        """
        Request completion suggestions
        
        Args:
            editor (QTextEdit): Editor to get completions for
        """
        try:
            # Get current context
            cursor = editor.textCursor()
            line = cursor.blockNumber()
            column = cursor.positionInBlock()
            text = editor.toPlainText()

            # Request completions from language server
            self.completer.request_completions(
                text=text,
                line=line,
                column=column,
                file_path=editor.file_path
            )

            self.logger.debug(
                f"[2025-02-16 16:04:56] Requested completions by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:04:56] Error requesting completions: {str(e)}"
            )


    def show_completion_suggestions(self, suggestions: List[Dict[str, Any]]):
        """
        Show code completion suggestions in popup
        
        Last modified: 2025-02-16 16:05:36
        Modified by: vcutrone
        
        Args:
            suggestions (List[Dict[str, Any]]): List of completion items with:
                - label: str
                - kind: str
                - detail: str (optional)
                - documentation: str (optional)
                - insertText: str
                - sortText: str (optional)
        """
        try:
            editor = self.current_editor()
            if not editor or not suggestions:
                return

            # Sort suggestions
            sorted_suggestions = self.sort_suggestions(suggestions)

            # Update completion list
            self.completion_list.clear()
            for suggestion in sorted_suggestions:
                self.completion_list.add_suggestion(
                    label=suggestion['label'],
                    kind=suggestion['kind'],
                    icon=self.get_suggestion_icon(suggestion['kind']),
                    insert_text=suggestion.get('insertText', suggestion['label'])
                )

            # Position popup
            cursor = editor.textCursor()
            rect = editor.cursorRect(cursor)
            global_pos = editor.mapToGlobal(rect.bottomLeft())

            self.completion_list.move(global_pos)
            self.completion_list.show()

            # Update info widget if available
            if self.completion_list.currentItem():
                self.update_completion_info(
                    sorted_suggestions[self.completion_list.currentRow()]
                )

            self.logger.debug(
                f"[2025-02-16 16:05:36] Showed completion suggestions by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:05:36] Error showing completion suggestions: {str(e)}"
            )


    def sort_suggestions(self, suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort completion suggestions by priority
        
        Args:
            suggestions: List of suggestion items
            
        Returns:
            List[Dict[str, Any]]: Sorted suggestions
        """
        try:
            def get_sort_key(item: Dict[str, Any]) -> Tuple[int, str]:
                # Priority order: variables, functions, classes, etc.
                kind_priority = {
                    'Variable': 0,
                    'Function': 1,
                    'Class': 2,
                    'Method': 3,
                    'Property': 4,
                    'Field': 5,
                    'Interface': 6,
                    'Module': 7,
                    'Keyword': 8,
                    'Snippet': 9
                }

                kind = item.get('kind', '')
                priority = kind_priority.get(kind, 99)

                # Use provided sort text or label
                sort_text = item.get('sortText', item['label'].lower())

                return (priority, sort_text)

            return sorted(suggestions, key=get_sort_key)

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:05:36] Error sorting suggestions: {str(e)}"
            )
            return suggestions


    def get_suggestion_icon(self, kind: str) -> QIcon:
        """
        Get appropriate icon for suggestion kind
        
        Args:
            kind (str): Type of suggestion
            
        Returns:
            QIcon: Icon for the suggestion type
        """
        try:
            icon_map = {
                'Variable': 'variable.png',
                'Function': 'function.png',
                'Class': 'class.png',
                'Method': 'method.png',
                'Property': 'property.png',
                'Field': 'field.png',
                'Interface': 'interface.png',
                'Module': 'module.png',
                'Keyword': 'keyword.png',
                'Snippet': 'snippet.png'
            }

            icon_path = os.path.join(
                self.resources_dir,
                'icons',
                icon_map.get(kind, 'default.png')
            )

            if os.path.exists(icon_path):
                return QIcon(icon_path)

            return QIcon()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:05:36] Error getting suggestion icon: {str(e)}"
            )
            return QIcon()


    def update_completion_info(self, suggestion: Dict[str, Any]):
        """
        Update completion info widget with details
        
        Args:
            suggestion (Dict[str, Any]): Selected suggestion item
        """
        try:
            # Build detailed info
            info = []

            if 'detail' in suggestion:
                info.append(f"<b>{suggestion['detail']}</b>")

            if 'documentation' in suggestion:
                info.append(suggestion['documentation'])

            if info:
                # Show info widget
                self.completion_info.setHtml(
                    "<br>".join(info)
                )

                # Position next to completion list
                list_pos = self.completion_list.pos()
                list_size = self.completion_list.size()

                self.completion_info.move(
                    list_pos.x() + list_size.width() + 5,
                    list_pos.y()
                )
                self.completion_info.show()
            else:
                self.completion_info.hide()

            self.logger.debug(
                f"[2025-02-16 16:05:36] Updated completion info by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:05:36] Error updating completion info: {str(e)}"
            )


    def wrap_key_press_event(self, editor: QTextEdit, original_event: Callable) -> Callable:
        """
        Wrap editor's key press event for completion handling
        
        Last modified: 2025-02-16 16:06:30
        Modified by: vcutrone
        
        Args:
            editor: Editor widget
            original_event: Original key press handler
            
        Returns:
            Callable: Wrapped event handler
        """

        def wrapped_event(event: QKeyEvent) -> None:
            try:
                # Handle completion navigation
                if self.completion_list.isVisible():
                    if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                        self.navigate_completion(event.key())
                        event.accept()
                        return

                    if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                        self.apply_completion()
                        event.accept()
                        return

                    if event.key() == Qt.Key.Key_Escape:
                        self.hide_completion()
                        event.accept()
                        return

                # Manual completion trigger
                if event.key() == Qt.Key.Key_Space and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                    self.request_completions(editor)
                    event.accept()
                    return

                # Call original handler
                original_event(event)

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 16:06:30] Error in key press event: {str(e)}"
                )
                original_event(event)

        return wrapped_event


    def navigate_completion(self, key: Qt.Key):
        """
        Navigate through completion suggestions
        
        Args:
            key: Navigation key pressed
        """
        try:
            current_row = self.completion_list.currentRow()
            max_row = self.completion_list.count() - 1

            if key == Qt.Key.Key_Up:
                new_row = max_row if current_row == 0 else current_row - 1
            else:  # Key_Down
                new_row = 0 if current_row == max_row else current_row + 1

            self.completion_list.setCurrentRow(new_row)

            # Update info widget
            current_item = self.completion_list.currentItem()
            if current_item:
                suggestion_data = current_item.data(Qt.ItemDataRole.UserRole)
                self.update_completion_info(suggestion_data)

            self.logger.debug(
                f"[2025-02-16 16:06:30] Navigated completion list by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:06:30] Error navigating completion: {str(e)}"
            )


    def apply_completion(self):
        """Apply selected completion suggestion"""
        try:
            editor = self.current_editor()
            if not editor:
                return

            current_item = self.completion_list.currentItem()
            if not current_item:
                return

            # Get completion data
            completion_data = current_item.data(Qt.ItemDataRole.UserRole)
            insert_text = completion_data.get('insertText', current_item.text())

            # Get cursor and current word
            cursor = editor.textCursor()
            current_word = self.get_current_word(cursor)

            # Remove current word
            if current_word:
                for _ in range(len(current_word)):
                    cursor.deletePreviousChar()

            # Insert completion text
            cursor.insertText(insert_text)

            # Hide completion widgets
            self.hide_completion()

            self.logger.debug(
                f"[2025-02-16 16:06:30] Applied completion by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:06:30] Error applying completion: {str(e)}"
            )


    def get_current_word(self, cursor: QTextCursor) -> str:
        """
        Get word at cursor position
        
        Args:
            cursor: Text cursor
            
        Returns:
            str: Current word
        """
        try:
            # Save cursor position
            pos = cursor.position()

            # Select word
            cursor.movePosition(
                QTextCursor.MoveOperation.StartOfWord,
                QTextCursor.MoveMode.MoveAnchor
            )
            cursor.movePosition(
                QTextCursor.MoveOperation.EndOfWord,
                QTextCursor.MoveMode.KeepAnchor
            )

            # Get selected text
            word = cursor.selectedText()

            # Restore cursor
            cursor.setPosition(pos)

            return word

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:06:30] Error getting current word: {str(e)}"
            )
            return ""


    def hide_completion(self):
        """
        Hide completion widgets
        
        Last modified: 2025-02-16 16:07:16
        Modified by: vcutrone
        """
        try:
            self.completion_list.hide()
            self.completion_info.hide()

            self.logger.debug(
                f"[2025-02-16 16:07:16] Hidden completion widgets by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:07:16] Error hiding completion: {str(e)}"
            )


    class CompletionListWidget(QListWidget):
        """Enhanced completion suggestion list widget"""

        def __init__(self, parent=None):
            super().__init__(parent)

            # Configure appearance
            self.setWindowFlags(
                Qt.WindowType.Popup |
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.NoDropShadowWindowHint
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            # Style settings
            self.setStyleSheet("""
                QListWidget {
                    background-color: #2b2b2b;
                    border: 1px solid #3c3c3c;
                    color: #d4d4d4;
                }
                QListWidget::item {
                    padding: 4px;
                }
                QListWidget::item:selected {
                    background-color: #3c3c3c;
                }
            """)

            # Connect signals
            self.itemClicked.connect(self.parent().apply_completion)

        def add_suggestion(self, label: str, kind: str, icon: QIcon, insert_text: str):
            """Add completion suggestion to list"""
            try:
                item = QListWidgetItem(icon, label)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    {
                        'label': label,
                        'kind': kind,
                        'insertText': insert_text
                    }
                )
                self.addItem(item)

            except Exception as e:
                logger.error(
                    f"[2025-02-16 16:07:16] Error adding completion suggestion: {str(e)}"
                )


    class CompletionInfoWidget(QLabel):
        """Enhanced completion detail information widget"""

        def __init__(self, parent=None):
            super().__init__(parent)

            # Configure appearance
            self.setWindowFlags(
                Qt.WindowType.Popup |
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.NoDropShadowWindowHint
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            # Style settings
            self.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 1px solid #3c3c3c;
                    color: #d4d4d4;
                    padding: 8px;
                }
            """)

            # Configure text display
            self.setTextFormat(Qt.TextFormat.RichText)
            self.setWordWrap(True)
            self.setMinimumWidth(200)
            self.setMaximumWidth(400)


    def wrap_focus_out_event(self, editor: QTextEdit, original_event: Callable) -> Callable:
        """
        Wrap editor's focus out event for completion handling
        
        Args:
            editor: Editor widget
            original_event: Original focus out handler
            
        Returns:
            Callable: Wrapped event handler
        """

        def wrapped_event(event: QFocusEvent) -> None:
            try:
                # Hide completion if focus moves outside editor
                if not self.completion_list.geometry().contains(QCursor.pos()):
                    self.hide_completion()

                # Call original handler
                original_event(event)

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 16:07:16] Error in focus out event: {str(e)}"
                )
                original_event(event)

        return wrapped_event


    def setup_code_intelligence(self):
        """Setup code intelligence features"""
        try:
            # Initialize language server client
            self.lsp_client = LanguageServerClient(
                parent=self,
                workspace_path=self.project_path,
                language_servers=self.get_language_servers()
            )

            # Create intelligence widget
            self.intelligence_widget = CodeIntelligenceWidget(self)

            # Create intelligence dock widget
            self.intelligence_dock = QDockWidget("Code Intelligence", self)
            self.intelligence_dock.setWidget(self.intelligence_widget)
            self.intelligence_dock.setAllowedAreas(
                Qt.DockWidgetArea.RightDockWidgetArea |
                Qt.DockWidgetArea.LeftDockWidgetArea
            )

            # Add dock widget
            self.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea,
                self.intelligence_dock
            )
            self.intelligence_dock.hide()  # Initially hidden

            # Connect signals
            self.connect_intelligence_signals()

            self.logger.info(
                f"[2025-02-16 16:07:16] Code intelligence setup by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:07:16] Error setting up code intelligence: {str(e)}"
            )


    def get_language_servers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get language server configurations
        
        Returns:
            Dict[str, Dict[str, Any]]: Language server settings
        """
        try:
            return {
                'python': {
                    'command': ['pylsp'],
                    'enabled': True,
                    'workspace_config': {
                        'pylsp': {
                            'plugins': {
                                'pycodestyle': {'enabled': True},
                                'pyflakes': {'enabled': True},
                                'rope_completion': {'enabled': True}
                            }
                        }
                    }
                },
                'javascript': {
                    'command': ['typescript-language-server', '--stdio'],
                    'enabled': True
                },
                'typescript': {
                    'command': ['typescript-language-server', '--stdio'],
                    'enabled': True
                },
                'java': {
                    'command': ['jdtls'],
                    'enabled': True
                }
            }

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:07:16] Error getting language servers: {str(e)}"
            )
            return {}


    def connect_intelligence_signals(self):
        """Connect code intelligence signals"""
        try:
            # LSP client signals
            self.lsp_client.diagnosticsReceived.connect(
                self.handle_diagnostics
            )
            self.lsp_client.completionsReceived.connect(
                self.handle_completions
            )
            self.lsp_client.definitionReceived.connect(
                self.handle_definition
            )
            self.lsp_client.referencesReceived.connect(
                self.handle_references
            )

            # Editor signals
            for editor in self.editors:
                editor.textChanged.connect(
                    lambda: self.handle_document_change(editor)
                )
                editor.cursorPositionChanged.connect(
                    lambda: self.handle_cursor_move(editor)
                )

            self.logger.debug(
                f"[2025-02-16 16:07:16] Connected intelligence signals by {CURRENT_USER}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:07:16] Error connecting intelligence signals: {str(e)}"
            )


    def handle_diagnostics(self, diagnostics: List[Dict[str, Any]]) -> None:
        """
        Handle diagnostic messages from language server
        
        Last modified: 2025-02-16 16:09:27
        Modified by: vcutrone
        
        Args:
            diagnostics: List of diagnostic messages containing:
                - severity: int (1=Error, 2=Warning, 3=Info)
                - message: str
                - range: Dict containing start and end positions
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Clear previous diagnostics
            editor.clear_diagnostic_markers()
            editor.diagnostic_messages.clear()

            # Process diagnostics by severity
            error_count = 0
            warning_count = 0
            info_count = 0

            for diagnostic in diagnostics:
                severity = diagnostic.get('severity', 1)
                message = diagnostic.get('message', '')
                range_ = diagnostic.get('range', {})
                start = range_.get('start', {})
                line = start.get('line', 0)

                # Add marker based on severity
                if severity == 1:  # Error
                    editor.add_error_marker(line, message)
                    error_count += 1
                elif severity == 2:  # Warning
                    editor.add_warning_marker(line, message)
                    warning_count += 1
                else:  # Info
                    editor.add_info_marker(line, message)
                    info_count += 1

                # Store message for tooltip
                editor.diagnostic_messages[line] = message

            # Update status message
            status_parts = []
            if error_count:
                status_parts.append(f"{error_count} error(s)")
            if warning_count:
                status_parts.append(f"{warning_count} warning(s)")
            if info_count:
                status_parts.append(f"{info_count} info(s)")

            status = "Diagnostics: " + ", ".join(status_parts) if status_parts else "No issues found"
            self.show_status_message(status)

            self.logger.debug(
                f"[2025-02-16 16:09:27] Handled {len(diagnostics)} diagnostics by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:09:27] Error handling diagnostics: {str(e)}"
            )


    def handle_completions(self, completions: List[Dict[str, Any]]) -> None:
        """
        Handle completion suggestions from language server
        
        Args:
            completions: List of completion items containing:
                - label: str
                - detail: str
                - kind: int
                - documentation: str (optional)
        """
        try:
            editor = self.current_editor()
            if not editor:
                return

            # Create completion list model
            model = QStandardItemModel()

            # Process sorted completions
            sorted_completions = sorted(
                completions,
                key=lambda x: (x.get('sortText', x.get('label', '')).lower())
            )

            for completion in sorted_completions:
                label = completion.get('label', '')
                detail = completion.get('detail', '')
                kind = completion.get('kind', 0)
                documentation = completion.get('documentation', '')

                # Create item with icon
                item = QStandardItem(self.get_completion_icon(kind), label)

                # Set tooltip with documentation
                tooltip = f"{label}"
                if detail:
                    tooltip += f"\n{detail}"
                if documentation:
                    tooltip += f"\n\n{documentation}"
                item.setToolTip(tooltip)

                # Store completion data
                item.setData(completion, Qt.ItemDataRole.UserRole)

                model.appendRow(item)

            # Update completion widget
            self.intelligence_widget.show_completions(model)

            self.logger.debug(
                f"[2025-02-16 16:09:27] Handled {len(completions)} completions by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:09:27] Error handling completions: {str(e)}"
            )


    def get_completion_icon(self, kind: int) -> QIcon:
        """
        Get appropriate icon for completion kind
        
        Last modified: 2025-02-16 16:10:37
        Modified by: vcutrone
        
        Args:
            kind: LSP completion kind ID
            
        Returns:
            QIcon: Icon for the completion type
        """
        try:
            # Map LSP completion kinds to icons
            icon_map = {
                1: "text.png",
                2: "method.png",
                3: "function.png",
                4: "constructor.png",
                5: "field.png",
                6: "variable.png",
                7: "class.png",
                8: "interface.png",
                9: "module.png",
                10: "property.png",
                11: "unit.png",
                12: "value.png",
                13: "enum.png",
                14: "keyword.png",
                15: "snippet.png",
                16: "color.png",
                17: "file.png",
                18: "reference.png"
            }

            # Get icon path
            icon_name = icon_map.get(kind, "default.png")
            icon_path = os.path.join(
                self.resources_dir,
                'icons',
                'completions',
                icon_name
            )

            # Return cached icon if available
            if icon_path in self._icon_cache:
                return self._icon_cache[icon_path]

            # Create and cache new icon
            icon = QIcon(icon_path)
            self._icon_cache[icon_path] = icon

            self.logger.debug(
                f"[2025-02-16 16:10:37] Created completion icon for kind {kind} by {vcutrone}"
            )

            return icon

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:10:37] Error getting completion icon: {str(e)}"
            )
            return QIcon()


    def handle_definition(self, definition: Optional[Dict[str, Any]]) -> None:
        """
        Handle go-to-definition response from language server
        
        Args:
            definition: Location information containing:
                - uri: str (file URI)
                - range: Dict with start and end positions
        """
        try:
            if not definition:
                self.show_status_message("No definition found")
                return

            # Extract location information
            uri = definition.get('uri', '')
            range_ = definition.get('range', {})
            start = range_.get('start', {})

            # Convert URI to file path
            file_path = uri.replace('file://', '')

            # Open file if needed
            current_editor = self.current_editor()
            if not current_editor or current_editor.file_path != file_path:
                self.open_file(file_path)

            editor = self.current_editor()
            if not editor:
                return

            # Move cursor to definition
            line = start.get('line', 0)
            character = start.get('character', 0)
            editor.goto_line_column(line, character)

            # Highlight definition
            editor.highlight_definition(
                line,
                character,
                duration_ms=1500
            )

            self.logger.debug(
                f"[2025-02-16 16:10:37] Jumped to definition in {file_path}:{line} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:10:37] Error handling definition: {str(e)}"
            )
            self.show_status_message("Failed to jump to definition", error=True)


    def setup_git_integration(self) -> None:
        """Setup Git integration features with enhanced UI"""
        try:
            # Initialize Git manager with configuration
            self.git_manager = GitManager(
                parent=self,
                auto_fetch=self.settings.value('git/auto_fetch', True),
                fetch_interval=self.settings.value('git/fetch_interval', 300),
                show_line_changes=self.settings.value('git/show_line_changes', True)
            )

            # Create Git widget with custom styling
            self.git_widget = GitWidget(
                parent=self,
                show_graph=True,
                show_stats=True,
                show_branches=True
            )

            # Apply custom styling
            self.git_widget.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #d4d4d4;
                }
                QTreeView {
                    border: 1px solid #3c3c3c;
                }
                QTreeView::item:selected {
                    background-color: #3c3c3c;
                }
            """)

            # Create Git dock widget
            self.git_dock = QDockWidget("Git", self)
            self.git_dock.setWidget(self.git_widget)
            self.git_dock.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea |
                Qt.DockWidgetArea.RightDockWidgetArea
            )

            # Add dock widget
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.git_dock)

            # Connect signals
            self._connect_git_signals()

            # Initial refresh
            self.git_widget.refresh_status()

            self.logger.info(
                f"[2025-02-16 16:10:37] Git integration setup by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:10:37] Error setting up Git integration: {str(e)}"
            )
            self.show_status_message("Failed to setup Git integration", error=True)


    def _connect_git_signals(self) -> None:
        """
        Connect Git-related signals and slots
        
        Last modified: 2025-02-16 16:11:32
        Modified by: vcutrone
        """
        try:
            # Git widget signals
            self.git_widget.commitRequested.connect(self.handle_git_commit)
            self.git_widget.pushRequested.connect(self.handle_git_push)
            self.git_widget.pullRequested.connect(self.handle_git_pull)
            self.git_widget.branchChanged.connect(self.handle_git_branch_change)
            self.git_widget.mergeRequested.connect(self.handle_git_merge)

            # Git manager signals
            self.git_manager.statusChanged.connect(self.git_widget.refresh_status)
            self.git_manager.errorOccurred.connect(
                lambda msg: self.show_status_message(f"Git error: {msg}", error=True)
            )

            # Setup auto-refresh timer
            self.git_refresh_timer = QTimer(self)
            self.git_refresh_timer.timeout.connect(self.git_widget.refresh_status)
            self.git_refresh_timer.start(30000)  # Refresh every 30 seconds

            self.logger.debug(
                f"[2025-02-16 16:11:32] Connected Git signals by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:11:32] Error connecting Git signals: {str(e)}"
            )


    def handle_git_commit(self, message: str) -> bool:
        """
        Handle Git commit request
        
        Args:
            message: Commit message
            
        Returns:
            bool: True if commit successful
        """
        try:
            # Validate commit message
            if not message.strip():
                self.show_status_message("Commit message required", error=True)
                return False

            # Save all modified files
            self.save_all_files()

            # Get repository path
            repo_path = self.git_manager.get_repository_path()
            if not repo_path:
                self.show_status_message("Not in a Git repository", error=True)
                return False

            # Stage changes
            staged = self.git_manager.stage_changes()
            if not staged:
                self.show_status_message("No changes to commit", error=True)
                return False

            # Perform commit
            success = self.git_manager.commit(
                message=message,
                author=f"{vcutrone} <{vcutrone}@domain.com>"
            )

            if success:
                self.show_status_message("Changes committed successfully")
                self.git_widget.refresh_status()
                return True

            self.show_status_message("Failed to commit changes", error=True)
            return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:11:32] Error handling Git commit: {str(e)}"
            )
            self.show_status_message(f"Commit error: {str(e)}", error=True)
            return False


    def handle_git_push(self) -> bool:
        """
        Handle Git push request
        
        Returns:
            bool: True if push successful
        """
        try:
            # Check for remote connection
            if not self.git_manager.has_remote():
                self.show_status_message("No remote repository configured", error=True)
                return False

            # Check for unpushed commits
            unpushed = self.git_manager.get_unpushed_commits()
            if not unpushed:
                self.show_status_message("No commits to push")
                return False

            # Show progress dialog
            progress = QProgressDialog("Pushing changes...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Perform push operation
                success = self.git_manager.push(
                    progress_callback=lambda x: progress.setValue(x)
                )

                if success:
                    self.show_status_message("Changes pushed successfully")
                    self.git_widget.refresh_status()
                    return True

                self.show_status_message("Failed to push changes", error=True)
                return False

            finally:
                progress.close()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:11:32] Error handling Git push: {str(e)}"
            )
            self.show_status_message(f"Push error: {str(e)}", error=True)
            return False


    def handle_git_pull(self) -> bool:
        """
        Handle Git pull request with merge conflict resolution
        
        Last modified: 2025-02-16 16:12:18
        Modified by: vcutrone
        
        Returns:
            bool: True if pull successful
        """
        try:
            # Check for remote connection
            if not self.git_manager.has_remote():
                self.show_status_message("No remote repository configured", error=True)
                return False

            # Check for local changes
            if self.git_manager.has_local_changes():
                response = self.show_confirmation_dialog(
                    title="Local Changes Detected",
                    message="There are unstaged changes. Choose an action:",
                    buttons=[
                        ("Stash Changes", QMessageBox.ButtonRole.YesRole),
                        ("Continue Without Stashing", QMessageBox.ButtonRole.NoRole),
                        ("Cancel", QMessageBox.ButtonRole.RejectRole)
                    ]
                )

                if response == QMessageBox.ButtonRole.RejectRole:
                    return False
                elif response == QMessageBox.ButtonRole.YesRole:
                    if not self.git_manager.stash_changes():
                        self.show_status_message("Failed to stash changes", error=True)
                        return False

            # Show progress dialog
            progress = QProgressDialog("Pulling changes...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Perform pull operation
                result = self.git_manager.pull(
                    progress_callback=lambda x: progress.setValue(x)
                )

                if result.success:
                    if result.files_updated:
                        self.refresh_editors(result.files_updated)
                    self.show_status_message(
                        f"Successfully pulled {result.commits_pulled} commits"
                    )
                    self.git_widget.refresh_status()
                    return True

                if result.has_conflicts:
                    self.handle_merge_conflicts(result.conflicts)
                else:
                    self.show_status_message(
                        f"Pull failed: {result.error_message}",
                        error=True
                    )
                return False

            finally:
                progress.close()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:18] Error handling Git pull: {str(e)}"
            )
            self.show_status_message(f"Pull error: {str(e)}", error=True)
            return False


    def handle_merge_conflicts(self, conflicts: List[Dict[str, Any]]) -> None:
        """
        Handle Git merge conflicts
        
        Args:
            conflicts: List of conflict information
        """
        try:
            # Show merge conflicts dialog
            dialog = MergeConflictsDialog(
                conflicts=conflicts,
                parent=self
            )

            if dialog.exec():
                # Apply resolved conflicts
                resolved = dialog.get_resolved_conflicts()
                if self.git_manager.apply_resolved_conflicts(resolved):
                    self.show_status_message("Merge conflicts resolved")
                    self.git_widget.refresh_status()
                else:
                    self.show_status_message(
                        "Failed to apply resolved conflicts",
                        error=True
                    )
            else:
                # Abort merge
                if self.git_manager.abort_merge():
                    self.show_status_message("Merge aborted")
                else:
                    self.show_status_message("Failed to abort merge", error=True)

            self.logger.debug(
                f"[2025-02-16 16:12:18] Handled merge conflicts by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:18] Error handling merge conflicts: {str(e)}"
            )
            self.show_status_message("Error resolving conflicts", error=True)


    def refresh_editors(self, updated_files: List[str]) -> None:
        """
        Refresh editors for updated files
        
        Args:
            updated_files: List of file paths that were updated
        """
        try:
            for file_path in updated_files:
                # Find editor for file
                editor = self.find_editor_by_path(file_path)
                if not editor:
                    continue

                # Get cursor position and scroll value
                cursor_position = editor.textCursor().position()
                scroll_value = editor.verticalScrollBar().value()

                # Reload file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Update editor content
                editor.setPlainText(content)

                # Restore cursor and scroll position
                cursor = editor.textCursor()
                cursor.setPosition(cursor_position)
                editor.setTextCursor(cursor)
                editor.verticalScrollBar().setValue(scroll_value)

            self.logger.debug(
                f"[2025-02-16 16:12:18] Refreshed {len(updated_files)} editors by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:18] Error refreshing editors: {str(e)}"
            )


    def setup_docker_integration(self) -> None:
        """
        Setup Docker integration with enhanced features
        
        Last modified: 2025-02-16 16:12:59
        Modified by: vcutrone
        """
        try:
            # Initialize Docker manager with configuration
            self.docker_manager = DockerManager(
                parent=self,
                auto_refresh=self.settings.value('docker/auto_refresh', True),
                refresh_interval=self.settings.value('docker/refresh_interval', 30)
            )

            # Create Docker widget with custom styling
            self.docker_widget = DockerWidget(
                parent=self,
                show_stats=True,
                show_logs=True
            )

            # Apply custom styling
            self.docker_widget.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #d4d4d4;
                }
                QTableView {
                    border: 1px solid #3c3c3c;
                    gridline-color: #3c3c3c;
                }
                QTableView::item:selected {
                    background-color: #3c3c3c;
                }
            """)

            # Create Docker dock widget
            self.docker_dock = QDockWidget("Docker", self)
            self.docker_dock.setWidget(self.docker_widget)
            self.docker_dock.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea |
                Qt.DockWidgetArea.RightDockWidgetArea
            )

            # Add dock widget
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.docker_dock)
            self.docker_dock.hide()  # Initially hidden

            # Connect signals
            self._connect_docker_signals()

            self.logger.info(
                f"[2025-02-16 16:12:59] Docker integration setup by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:59] Error setting up Docker integration: {str(e)}"
            )


    def _connect_docker_signals(self) -> None:
        """Connect Docker-related signals and slots"""
        try:
            # Docker widget signals
            self.docker_widget.buildRequested.connect(self.handle_docker_build)
            self.docker_widget.runRequested.connect(self.handle_docker_run)
            self.docker_widget.stopRequested.connect(self.handle_docker_stop)
            self.docker_widget.removeRequested.connect(self.handle_docker_remove)

            # Docker manager signals
            self.docker_manager.statusChanged.connect(self.docker_widget.refresh_status)
            self.docker_manager.errorOccurred.connect(
                lambda msg: self.show_status_message(f"Docker error: {msg}", error=True)
            )

            self.logger.debug(
                f"[2025-02-16 16:12:59] Connected Docker signals by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:59] Error connecting Docker signals: {str(e)}"
            )


    def handle_docker_build(self, dockerfile_path: str) -> bool:
        """
        Handle Docker build request
        
        Args:
            dockerfile_path: Path to Dockerfile
            
        Returns:
            bool: True if build successful
        """
        try:
            # Validate Dockerfile exists
            if not os.path.exists(dockerfile_path):
                self.show_status_message("Dockerfile not found", error=True)
                return False

            # Get image configuration
            config = DockerBuildConfigDialog.get_config(self)
            if not config:
                return False

            # Show build progress dialog
            progress = QProgressDialog("Building Docker image...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Start build process
                result = self.docker_manager.build_image(
                    dockerfile_path=dockerfile_path,
                    tag=config['tag'],
                    build_args=config['build_args'],
                    progress_callback=lambda x: progress.setValue(x)
                )

                if result.success:
                    self.show_status_message(
                        f"Successfully built Docker image: {config['tag']}"
                    )
                    self.docker_widget.refresh_images()
                    return True

                self.show_status_message(
                    f"Build failed: {result.error_message}",
                    error=True
                )
                return False

            finally:
                progress.close()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:59] Error handling Docker build: {str(e)}"
            )
            self.show_status_message(f"Build error: {str(e)}", error=True)
            return False


    def handle_docker_run(self, image_name: str) -> bool:
        """
        Handle Docker run request
        
        Args:
            image_name: Name of Docker image to run
            
        Returns:
            bool: True if container started successfully
        """
        try:
            # Get container configuration
            config = DockerRunConfigDialog.get_config(self)
            if not config:
                return False

            # Validate configuration
            if not self.docker_manager.validate_config(config):
                self.show_status_message("Invalid container configuration", error=True)
                return False

            # Start container
            container_id = self.docker_manager.run_container(
                image_name=image_name,
                config=config
            )

            if container_id:
                self.show_status_message(
                    f"Container started: {container_id[:12]}"
                )
                self.docker_widget.refresh_containers()

                # Show container logs if requested
                if config.get('show_logs', False):
                    self.show_container_logs(container_id)

                return True

            self.show_status_message("Failed to start container", error=True)
            return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:59] Error handling Docker run: {str(e)}"
            )
            self.show_status_message(f"Run error: {str(e)}", error=True)
            return False


    def show_container_logs(self, container_id: str) -> None:
        """
        Show Docker container logs
        
        Args:
            container_id: Container ID to show logs for
        """
        try:
            # Create logs dialog
            dialog = DockerLogsDialog(
                container_id=container_id,
                docker_manager=self.docker_manager,
                parent=self
            )

            # Show non-modal dialog
            dialog.show()

            self.logger.debug(
                f"[2025-02-16 16:12:59] Showing container logs by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:12:59] Error showing container logs: {str(e)}"
            )
            self.show_status_message("Failed to show container logs", error=True)


    def update_git_status(self) -> None:
        """
        Update Git status information
        
        Last modified: 2025-02-16 16:15:14
        Modified by: vcutrone
        """
        try:
            # Get current git status with cache check
            status = self.git_manager.get_status(use_cache=True)
            if not status:
                return

            # Update status display with changes
            self.git_widget.update_status(status)

            # Update file markers efficiently
            for editor in self.editors:
                if not editor.file_path:
                    continue

                file_status = status.get(editor.file_path, {})
                if file_status:
                    editor.update_git_markers(file_status)

            # Update window title with branch info
            if branch := status.get('branch'):
                self.update_window_title(branch=branch)

            self.logger.debug(
                f"[2025-02-16 16:15:14] Updated git status by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:15:14] Error updating git status: {str(e)}"
            )


    def handle_branch_change(self, branch_name: str) -> bool:
        """
        Handle Git branch change with safety checks
        
        Args:
            branch_name: Name of branch to switch to
            
        Returns:
            bool: True if branch change successful
        """
        try:
            # Validate branch name
            if not branch_name or not isinstance(branch_name, str):
                self.show_status_message("Invalid branch name", error=True)
                return False

            # Check for unsaved changes
            if self.has_unsaved_changes():
                response = self.show_confirmation_dialog(
                    title="Unsaved Changes",
                    message=f"You have unsaved changes. Switch to branch '{branch_name}' anyway?",
                    buttons=[
                        ("Switch Branch", QMessageBox.ButtonRole.YesRole),
                        ("Cancel", QMessageBox.ButtonRole.NoRole)
                    ]
                )

                if response == QMessageBox.ButtonRole.NoRole:
                    return False

            # Start branch change
            self.show_status_message(f"Switching to branch: {branch_name}...")

            # Change branch
            success = self.git_manager.change_branch(
                branch_name,
                progress_callback=self.update_progress_bar
            )

            if success:
                # Reload files
                self.reload_all_files()
                self.update_git_status()
                self.show_status_message(f"Switched to branch: {branch_name}")
                return True

            self.show_status_message("Failed to change branch", error=True)
            return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:15:14] Error changing git branch: {str(e)}"
            )
            self.show_status_message(f"Branch change error: {str(e)}", error=True)
            return False


    def handle_commit_select(self, commit_hash: str) -> None:
        """
        Handle Git commit selection and details display
        
        Args:
            commit_hash: Hash of selected commit
        """
        try:
            # Validate commit hash
            if not commit_hash or not isinstance(commit_hash, str):
                return

            # Get detailed commit info
            commit_info = self.git_manager.get_commit_info(
                commit_hash,
                include_diff=self.settings.value('git/include_diff_in_details', True)
            )

            if not commit_info:
                return

            # Show commit details in git widget
            self.git_widget.show_commit_details(commit_info)

            # Load diff view if configured
            if self.settings.value('git/auto_load_commit_diff', True):
                self.load_commit_diff(commit_hash)

            self.logger.debug(
                f"[2025-02-16 16:15:14] Selected git commit {commit_hash[:8]} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:15:14] Error handling commit selection: {str(e)}"
            )
            self.show_status_message("Failed to load commit details", error=True)


    def load_commit_diff(self, commit_hash: str) -> None:
        """
        Load and display commit diff viewer
        
        Last modified: 2025-02-16 16:15:55
        Modified by: vcutrone
        
        Args:
            commit_hash: Hash of commit to display diff for
        """
        try:
            # Validate commit hash
            if not commit_hash or not isinstance(commit_hash, str):
                return

            # Get commit diff with progress
            progress = QProgressDialog("Loading diff...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                diff_data = self.git_manager.get_commit_diff(
                    commit_hash,
                    context_lines=self.settings.value('git/diff_context_lines', 3),
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if not diff_data:
                return

            # Create or reuse diff viewer
            if not hasattr(self, 'diff_viewer'):
                self.diff_viewer = DiffViewer(
                    parent=self,
                    syntax_highlighting=True,
                    word_wrap=self.settings.value('git/diff_word_wrap', False),
                    show_line_numbers=True
                )

                self.diff_dock = QDockWidget("Diff Viewer", self)
                self.diff_dock.setWidget(self.diff_viewer)
                self.diff_dock.setAllowedAreas(
                    Qt.DockWidgetArea.BottomDockWidgetArea |
                    Qt.DockWidgetArea.RightDockWidgetArea
                )

                self.addDockWidget(
                    Qt.DockWidgetArea.BottomDockWidgetArea,
                    self.diff_dock
                )

            # Show diff with custom styling
            self.diff_viewer.show_diff(
                diff_data,
                commit_info=self.git_manager.get_commit_info(commit_hash)
            )
            self.diff_dock.show()
            self.diff_dock.raise_()

            self.logger.debug(
                f"[2025-02-16 16:15:55] Loaded commit diff for {commit_hash[:8]} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:15:55] Error loading commit diff: {str(e)}"
            )
            self.show_status_message("Failed to load diff view", error=True)


    def handle_stage_files(self, file_paths: List[str]) -> bool:
        """
        Handle staging of files for commit
        
        Args:
            file_paths: List of file paths to stage
            
        Returns:
            bool: True if files staged successfully
        """
        try:
            # Validate input
            if not file_paths or not isinstance(file_paths, list):
                return False

            # Filter valid paths
            valid_paths = [
                path for path in file_paths
                if path and isinstance(path, str) and os.path.exists(path)
            ]

            if not valid_paths:
                self.show_status_message("No valid files to stage", error=True)
                return False

            # Stage files with progress
            progress = QProgressDialog("Staging files...", "Cancel", 0, len(valid_paths), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                staged_files = self.git_manager.stage_files(
                    valid_paths,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if staged_files:
                # Update git widget
                self.git_widget.update_staged_files(staged_files)

                # Update status
                self.update_git_status()

                # Show status message
                self.show_status_message(f"Staged {len(staged_files)} file(s)")
                return True

            self.show_status_message("No files were staged", warning=True)
            return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:15:55] Error staging files: {str(e)}"
            )
            self.show_status_message(f"Failed to stage files: {str(e)}", error=True)
            return False


    def setup_project_explorer(self) -> None:
        """Setup project explorer with enhanced features"""
        try:
            # Create project explorer with custom configuration
            self.project_explorer = ProjectExplorerWidget(
                parent=self,
                show_hidden=self.settings.value('explorer/show_hidden', False),
                file_filters=self.settings.value('explorer/file_filters', []),
                sort_folders_first=True
            )

            # Apply custom styling
            self.project_explorer.setStyleSheet("""
                QTreeView {
                    background-color: #2b2b2b;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                }
                QTreeView::item:selected {
                    background-color: #3c3c3c;
                }
                QTreeView::item:hover {
                    background-color: #323232;
                }
            """)

            # Create project dock widget
            self.project_dock = QDockWidget("Project Explorer", self)
            self.project_dock.setWidget(self.project_explorer)
            self.project_dock.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea |
                Qt.DockWidgetArea.RightDockWidgetArea
            )

            # Add dock widget
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)

            # Connect signals
            self._connect_project_explorer_signals()

            # Setup file system watcher
            self._setup_fs_watcher()

            self.logger.info(
                f"[2025-02-16 16:15:55] Project explorer setup by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:15:55] Error setting up project explorer: {str(e)}"
            )


    def _connect_project_explorer_signals(self) -> None:
        """
        Connect project explorer signals and slots
        
        Last modified: 2025-02-16 16:16:54
        Modified by: vcutrone
        """
        try:
            # File operations
            self.project_explorer.fileSelected.connect(self.open_file)
            self.project_explorer.fileRenamed.connect(self.handle_file_rename)
            self.project_explorer.fileDeleted.connect(self.handle_file_delete)
            self.project_explorer.fileMoved.connect(self.handle_file_move)

            # Directory operations
            self.project_explorer.directoryCreated.connect(self.handle_directory_create)
            self.project_explorer.directoryDeleted.connect(self.handle_directory_delete)
            self.project_explorer.directoryRenamed.connect(self.handle_directory_rename)

            # Context menu actions
            self.project_explorer.openInTerminal.connect(self.open_terminal_at_path)
            self.project_explorer.openInExplorer.connect(self.open_in_file_explorer)
            self.project_explorer.gitOperationRequested.connect(self.handle_git_operation)

            self.logger.debug(
                f"[2025-02-16 16:16:54] Connected project explorer signals by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:16:54] Error connecting project explorer signals: {str(e)}"
            )


    def _setup_fs_watcher(self) -> None:
        """Setup file system watcher with debouncing"""
        try:
            self.fs_watcher = QFileSystemWatcher(self)

            # Setup debounce timers
            self.dir_change_timer = QTimer(self)
            self.dir_change_timer.setSingleShot(True)
            self.dir_change_timer.timeout.connect(self._handle_pending_dir_changes)

            self.file_change_timer = QTimer(self)
            self.file_change_timer.setSingleShot(True)
            self.file_change_timer.timeout.connect(self._handle_pending_file_changes)

            # Initialize change queues
            self.pending_dir_changes: Set[str] = set()
            self.pending_file_changes: Set[str] = set()

            # Connect watcher signals with debouncing
            self.fs_watcher.directoryChanged.connect(self._queue_directory_change)
            self.fs_watcher.fileChanged.connect(self._queue_file_change)

            self.logger.debug(
                f"[2025-02-16 16:16:54] Setup file system watcher by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:16:54] Error setting up file system watcher: {str(e)}"
            )


    def _queue_directory_change(self, path: str) -> None:
        """
        Queue directory change for debounced processing
        
        Args:
            path: Directory path that changed
        """
        try:
            self.pending_dir_changes.add(path)
            self.dir_change_timer.start(100)  # 100ms debounce

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:16:54] Error queuing directory change: {str(e)}"
            )


    def _queue_file_change(self, path: str) -> None:
        """
        Queue file change for debounced processing
        
        Args:
            path: File path that changed
        """
        try:
            self.pending_file_changes.add(path)
            self.file_change_timer.start(100)  # 100ms debounce

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:16:54] Error queuing file change: {str(e)}"
            )


    def _handle_pending_dir_changes(self) -> None:
        """Process pending directory changes"""
        try:
            # Process all queued directory changes
            for path in self.pending_dir_changes:
                self.handle_fs_change(path)

            # Clear queue
            self.pending_dir_changes.clear()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:16:54] Error handling pending directory changes: {str(e)}"
            )


    def _handle_pending_file_changes(self) -> None:
        """Process pending file changes"""
        try:
            # Process all queued file changes
            for path in self.pending_file_changes:
                self.handle_file_change(path)

            # Clear queue
            self.pending_file_changes.clear()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:16:54] Error handling pending file changes: {str(e)}"
            )


    def handle_fs_change(self, path: str) -> None:
        """
        Handle file system directory changes
        
        Last modified: 2025-02-16 16:17:32
        Modified by: vcutrone
        
        Args:
            path: Directory path that changed
        """
        try:
            # Skip if path no longer exists
            if not os.path.exists(path):
                self.fs_watcher.removePath(path)
                return

            # Update project explorer efficiently
            self.project_explorer.refresh_directory(
                path,
                recursive=False,  # Avoid expensive recursive refresh
                emit_signals=False  # Batch update signals
            )

            # Update git status if path is in git repo
            if self.git_manager.is_git_path(path):
                self.update_git_status()

            self.logger.debug(
                f"[2025-02-16 16:17:32] Handled directory change: {path} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:17:32] Error handling directory change: {str(e)}"
            )


    def handle_file_change(self, file_path: str) -> None:
        """
        Handle file system file changes with conflict resolution
        
        Args:
            file_path: Path of changed file
        """
        try:
            # Get editor for file if open
            editor = self.get_editor_by_path(file_path)
            if not editor:
                return

            # Check if file still exists
            if not os.path.exists(file_path):
                self.handle_file_deleted(file_path)
                return

            # Check for external modifications
            if editor.is_externally_modified():
                if editor.is_dirty():
                    # File modified both externally and in editor
                    response = self.show_conflict_resolution_dialog(file_path)
                    self.handle_file_conflict(editor, response)
                else:
                    # File only modified externally
                    self.reload_file_with_confirmation(editor)

            # Update project explorer
            self.project_explorer.refresh_file(file_path)

            # Update git status if file is in git repo
            if self.git_manager.is_git_path(file_path):
                self.update_git_status()

            self.logger.debug(
                f"[2025-02-16 16:17:32] Handled file change: {file_path} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:17:32] Error handling file change: {str(e)}"
            )


    def handle_file_conflict(self, editor: 'Editor', response: str) -> None:
        """
        Handle file modification conflict
        
        Args:
            editor: Editor instance with conflict
            response: User's conflict resolution choice
        """
        try:
            if response == "keep_editor":
                # Keep editor changes, mark file for save
                editor.mark_for_save()
            elif response == "keep_disk":
                # Reload file from disk
                editor.reload_file(preserve_undo=True)
            elif response == "merge":
                # Show merge dialog
                self.show_merge_dialog(editor)

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:17:32] Error handling file conflict: {str(e)}"
            )
            self.show_status_message("Failed to resolve file conflict", error=True)


    def show_conflict_resolution_dialog(self, file_path: str) -> str:
        """
        Show dialog for resolving file conflicts
        
        Args:
            file_path: Path of file with conflict
            
        Returns:
            str: User's choice ('keep_editor', 'keep_disk', 'merge', or 'cancel')
        """
        try:
            dialog = QMessageBox(self)
            dialog.setWindowTitle("File Conflict")
            dialog.setText(
                f"File '{os.path.basename(file_path)}' has been modified externally "
                "and has unsaved changes in the editor."
            )
            dialog.setInformativeText("How would you like to resolve this conflict?")

            # Add custom buttons
            keep_editor = dialog.addButton(
                "Keep Editor Changes",
                QMessageBox.ButtonRole.AcceptRole
            )
            keep_disk = dialog.addButton(
                "Keep Disk Changes",
                QMessageBox.ButtonRole.RejectRole
            )
            merge = dialog.addButton(
                "Merge Changes",
                QMessageBox.ButtonRole.ActionRole
            )
            dialog.addButton(
                QMessageBox.StandardButton.Cancel
            )

            dialog.exec()
            clicked = dialog.clickedButton()

            if clicked == keep_editor:
                return "keep_editor"
            elif clicked == keep_disk:
                return "keep_disk"
            elif clicked == merge:
                return "merge"

            return "cancel"

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:17:32] Error showing conflict dialog: {str(e)}"
            )
            return "cancel"


    def reload_file_with_confirmation(self, editor: 'Editor') -> bool:
        """
        Reload file with user confirmation
        
        Last modified: 2025-02-16 16:18:16
        Modified by: vcutrone
        
        Args:
            editor: Editor instance to reload
            
        Returns:
            bool: True if file was reloaded
        """
        try:
            response = QMessageBox.question(
                self,
                "File Modified",
                f"File '{os.path.basename(editor.file_path)}' was modified externally. Reload?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes  # Default to Yes
            )

            if response == QMessageBox.StandardButton.Yes:
                # Save cursor position and scroll state
                cursor_pos = editor.textCursor().position()
                scroll_pos = editor.verticalScrollBar().value()

                # Reload file
                success = editor.reload_file(preserve_undo=True)

                if success:
                    # Restore cursor and scroll position
                    cursor = editor.textCursor()
                    cursor.setPosition(cursor_pos)
                    editor.setTextCursor(cursor)
                    editor.verticalScrollBar().setValue(scroll_pos)

                    self.show_status_message("File reloaded successfully")
                    return True

            return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:18:16] Error reloading file: {str(e)}"
            )
            self.show_status_message("Failed to reload file", error=True)
            return False


    def show_merge_dialog(self, editor: 'Editor') -> None:
        """
        Show three-way merge dialog for resolving conflicts
        
        Args:
            editor: Editor instance with conflict
        """
        try:
            # Create merge dialog
            dialog = MergeDialog(
                parent=self,
                local_content=editor.toPlainText(),
                disk_content=editor.read_file_content(),
                base_content=editor.get_last_saved_content(),
                file_path=editor.file_path
            )

            # Apply custom styling
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: #d4d4d4;
                }
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                }
                QPushButton {
                    background-color: #0e639c;
                    color: white;
                    border: none;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
            """)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Apply merged content
                editor.setPlainText(dialog.get_merged_content())
                editor.mark_for_save()

                self.show_status_message("Changes merged successfully")

            self.logger.debug(
                f"[2025-02-16 16:18:16] Showed merge dialog for {editor.file_path} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:18:16] Error showing merge dialog: {str(e)}"
            )
            self.show_status_message("Failed to show merge dialog", error=True)


    def handle_file_deleted(self, file_path: str) -> None:
        """
        Handle file deletion event
        
        Args:
            file_path: Path of deleted file
        """
        try:
            # Get editor if file is open
            editor = self.get_editor_by_path(file_path)
            if not editor:
                return

            # Ask user what to do
            response = QMessageBox.question(
                self,
                "File Deleted",
                f"File '{os.path.basename(file_path)}' has been deleted. "
                "What would you like to do?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Close |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if response == QMessageBox.StandardButton.Save:
                # Try to save the file
                if editor.save():
                    self.show_status_message("File restored and saved")
                else:
                    self.show_status_message("Failed to save file", error=True)

            elif response == QMessageBox.StandardButton.Close:
                # Close the editor
                self.close_editor(editor)

            # Update project explorer
            self.project_explorer.refresh_parent_dir(file_path)

            # Update git status if needed
            if self.git_manager and self.git_manager.is_git_path(file_path):
                self.update_git_status()

            self.logger.debug(
                f"[2025-02-16 16:18:16] Handled file deletion: {file_path} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:18:16] Error handling file deletion: {str(e)}"
            )
            self.show_status_message("Failed to handle file deletion", error=True)


    def handle_directory_create(self, path: str) -> None:
        """
        Handle directory creation event
        
        Args:
            path: Path of created directory
        """
        try:
            # Update project explorer
            self.project_explorer.refresh_parent_dir(path)

            # Add to file system watcher
            self.fs_watcher.addPath(path)

            # Update git status if in repo
            if self.git_manager and self.git_manager.is_git_path(path):
                self.update_git_status()

            self.show_status_message(f"Created directory: {os.path.basename(path)}")

            self.logger.debug(
                f"[2025-02-16 16:18:16] Created directory: {path} by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:18:16] Error handling directory creation: {str(e)}"
            )
            self.show_status_message("Failed to handle directory creation", error=True)


    def save_debug_output(self) -> bool:
        """
        Save debug session output to file
        
        Last modified: 2025-02-16 16:20:46
        Modified by: vcutrone
        
        Returns:
            bool: True if output was saved successfully
        """
        try:
            # Create debug output directory
            output_dir = os.path.join(self.project_root, '.vscode', 'debug-output')
            os.makedirs(output_dir, exist_ok=True)

            # Generate output filename
            config_name = self.debugger.get_current_configuration().get('name', 'unknown')
            timestamp = self.debug_start_time.strftime('%Y%m%d_%H%M%S')
            filename = f"debug_{config_name}_{timestamp}.log"
            output_path = os.path.join(output_dir, filename)

            # Get debug session output
            output_text = self.debugger.get_output()

            # Generate session summary
            duration = datetime.now() - self.debug_start_time
            summary = f"""Debug Session Summary
    ====================
    Configuration: {config_name}
    Start Time: {self.debug_start_time}
    Duration: {duration.total_seconds():.1f}s
    Project: {self.project_root}
    User: {vcutrone}
    Timestamp: {datetime.now()}

    """

            # Save output with summary
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(summary)
                f.write(output_text)

            self.logger.debug(
                f"[2025-02-16 16:20:46] Debug output saved to {output_path} by {vcutrone}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:20:46] Error saving debug output: {str(e)}"
            )
            self.show_status_message("Failed to save debug output", error=True)
            return False


    def clear_debug_decorations(self) -> None:
        """Clear all debug-related decorations and highlights"""
        try:
            # Clear debug line highlights in all editors
            for editor in self.get_all_editors():
                editor.clear_debug_line_highlight()
                editor.clear_error_line_highlight()
                editor.clear_breakpoint_highlights()

            # Clear debug views
            self.debugger.variables_view.clear()
            self.debugger.watch_view.clear()
            self.debugger.call_stack_view.clear()
            self.debugger.breakpoints_view.clear()

            # Reset debug status
            self.show_status_message("Debug session ended")

            self.logger.debug(
                f"[2025-02-16 16:20:46] Cleared debug decorations by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:20:46] Error clearing debug decorations: {str(e)}"
            )


    def update_debug_actions(self, debugging_active: bool) -> None:
        """
        Update debug-related actions based on debug state
        
        Args:
            debugging_active: Whether debugging is currently active
        """
        try:
            # Define action groups
            debug_actions = {
                'shortcuts': [
                    self.stop_debug_shortcut,
                    self.step_over_shortcut,
                    self.step_into_shortcut,
                    self.step_out_shortcut
                ],
                'menu_items': [
                    self.debug_menu.actions()[1],  # Stop
                    self.debug_menu.actions()[3],  # Step Over
                    self.debug_menu.actions()[4],  # Step Into
                    self.debug_menu.actions()[5]  # Step Out
                ],
                'toolbar_items': [
                    self.debug_toolbar.actions()[1],  # Stop
                    self.debug_toolbar.actions()[3],  # Step Over
                    self.debug_toolbar.actions()[4],  # Step Into
                    self.debug_toolbar.actions()[5]  # Step Out
                ]
            }

            # Update all actions
            for group in debug_actions.values():
                for action in group:
                    action.setEnabled(debugging_active)

            # Update debug views visibility
            self.variables_dock.setVisible(debugging_active)
            self.watch_dock.setVisible(debugging_active)
            self.call_stack_dock.setVisible(debugging_active)

            self.logger.debug(
                f"[2025-02-16 16:20:46] Updated debug actions (active={debugging_active}) by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:20:46] Error updating debug actions: {str(e)}"
            )


    def setup_git(self) -> None:
        """
        Setup Git integration with enhanced features
        
        Last modified: 2025-02-16 16:21:25
        Modified by: vcutrone
        """
        try:
            # Create git widget with configuration
            self.git_widget = GitWidget(
                parent=self,
                show_graph=True,
                show_stats=True,
                show_diff=True
            )

            # Apply custom styling
            self.git_widget.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #d4d4d4;
                }
                QTreeView {
                    border: 1px solid #3c3c3c;
                }
                QTreeView::item:selected {
                    background-color: #3c3c3c;
                }
                QPushButton {
                    background-color: #0e639c;
                    color: white;
                    border: none;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
            """)

            # Create git dock widget
            self.git_dock = QDockWidget("Git", self)
            self.git_dock.setWidget(self.git_widget)
            self.git_dock.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea |
                Qt.DockWidgetArea.RightDockWidgetArea
            )

            # Add dock widget
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.git_dock)

            # Connect signals
            self._connect_git_signals()

            # Initialize repository if in project
            if self.project_root:
                self.init_git_repo()

            self.logger.info(
                f"[2025-02-16 16:21:25] Git integration setup by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:21:25] Error setting up Git integration: {str(e)}"
            )


    def _connect_git_signals(self) -> None:
        """Connect Git-related signals"""
        try:
            # Status changes
            self.git_widget.statusChanged.connect(self.handle_git_status_changed)

            # Commit operations
            self.git_widget.commitCreated.connect(self.handle_git_commit)
            self.git_widget.commitSelected.connect(self.handle_commit_select)

            # Branch operations
            self.git_widget.branchChanged.connect(self.handle_branch_changed)
            self.git_widget.branchCreated.connect(self.update_branch_menu)
            self.git_widget.branchDeleted.connect(self.update_branch_menu)

            # Remote operations
            self.git_widget.pushCompleted.connect(self.handle_git_push)
            self.git_widget.pullCompleted.connect(self.handle_git_pull)
            self.git_widget.fetchCompleted.connect(self.update_remote_tracking)

            # Conflict handling
            self.git_widget.mergeConflict.connect(self.handle_git_merge_conflict)
            self.git_widget.conflictResolved.connect(self.handle_conflict_resolved)

            self.logger.debug(
                f"[2025-02-16 16:21:25] Connected Git signals by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:21:25] Error connecting Git signals: {str(e)}"
            )


    def init_git_repo(self) -> bool:
        """
        Initialize Git repository integration
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Verify git repository
            git_dir = os.path.join(self.project_root, '.git')
            if not os.path.exists(git_dir):
                self.show_status_message("Not a Git repository")
                self.git_dock.hide()
                return False

            # Initialize repository
            success = self.git_widget.initialize_repository(
                self.project_root,
                watch_changes=True
            )

            if not success:
                self.show_status_message("Failed to initialize Git repository", error=True)
                return False

            # Setup git file watchers
            git_patterns = [
                '.git/HEAD',
                '.git/index',
                '.git/refs/heads/*',
                '.git/refs/remotes/*'
            ]

            for pattern in git_patterns:
                path = os.path.join(self.project_root, pattern)
                self.fs_watcher.addPath(path)

            # Load configurations
            self.load_git_config()

            # Initialize branch tracking
            self.current_branch = self.git_widget.get_current_branch()
            self.remote_branches = self.git_widget.get_remote_branches()

            # Setup git gutter for all editors
            for editor in self.get_all_editors():
                editor.setup_git_gutter(self.git_widget)

            # Initial status update
            self.update_git_status()

            self.logger.debug(
                f"[2025-02-16 16:21:25] Initialized Git repo: {self.project_root} by {vcutrone}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:21:25] Error initializing Git repo: {str(e)}"
            )
            self.show_status_message("Failed to initialize Git repository", error=True)
            return False


    def load_git_config(self) -> Dict[str, Any]:
        """
        Load Git configuration settings from global and local configs
        
        Last modified: 2025-02-16 16:22:08
        Modified by: vcutrone
        
        Returns:
            Dict[str, Any]: Merged configuration dictionary
        """
        try:
            # Load global git configuration
            global_config: Dict[str, Any] = {}
            git_config_path = os.path.expanduser('~/.gitconfig')

            if os.path.exists(git_config_path):
                with open(git_config_path, 'r', encoding='utf-8') as f:
                    global_config = self.parse_git_config(f.read())

            # Load repository git configuration
            repo_config: Dict[str, Any] = {}
            local_config_path = os.path.join(self.project_root, '.git/config')

            if os.path.exists(local_config_path):
                with open(local_config_path, 'r', encoding='utf-8') as f:
                    repo_config = self.parse_git_config(f.read())

            # Merge configurations (repo config takes precedence)
            merged_config = {**global_config, **repo_config}

            # Configure git widget
            self.git_widget.set_configuration(merged_config)

            # Store important settings
            self.git_user = merged_config.get('user.name', '')
            self.git_email = merged_config.get('user.email', '')
            self.git_remote = merged_config.get('remote.origin.url', '')

            self.logger.debug(
                f"[2025-02-16 16:22:08] Loaded Git config by {vcutrone}: "
                f"user={self.git_user}, remote={self.git_remote}"
            )

            return merged_config

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:22:08] Error loading Git config: {str(e)}"
            )
            return {}


    def parse_git_config(self, config_text: str) -> Dict[str, str]:
        """
        Parse Git configuration file content
        
        Args:
            config_text: Raw configuration file content
            
        Returns:
            Dict[str, str]: Parsed configuration dictionary
        """
        try:
            config: Dict[str, str] = {}
            current_section: Optional[str] = None

            for line in config_text.splitlines():
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Handle section headers
                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1]
                    # Handle subsections
                    if ' "' in section:
                        section = section.replace(' "', '.').rstrip('"')
                    current_section = section.lower()
                    continue

                # Handle key-value pairs
                if '=' in line and current_section:
                    key, value = map(str.strip, line.split('=', 1))
                    value = value.strip('"\'')

                    # Create full key with section
                    full_key = f"{current_section}.{key}"
                    config[full_key] = value

            return config

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:22:08] Error parsing Git config: {str(e)}"
            )
            return {}


    def update_git_status(self) -> None:
        """Update Git status information and UI elements"""
        try:
            # Get current status with cache
            status = self.git_widget.get_repository_status(use_cache=True)

            if not status:
                return

            # Update branch information
            new_branch = status.get('branch')
            if new_branch and new_branch != self.current_branch:
                self.current_branch = new_branch
                self.handle_branch_changed(new_branch)

            # Extract file statuses
            modified_files = status.get('modified', [])
            staged_files = status.get('staged', [])
            untracked_files = status.get('untracked', [])

            # Update editor gutters efficiently
            for editor in self.get_all_editors():
                if not editor.file_path:
                    continue

                relative_path = os.path.relpath(editor.file_path, self.project_root)
                editor.update_git_status(
                    modified=(relative_path in modified_files),
                    staged=(relative_path in staged_files),
                    untracked=(relative_path in untracked_files)
                )

            # Update status bar with branch info
            status_text = [f"Git: {self.current_branch}"]
            if staged_files:
                status_text.append(f"{len(staged_files)}↑")
            if modified_files:
                status_text.append(f"{len(modified_files)}*")

            self.git_status_label.setText(" ".join(status_text))

            self.logger.debug(
                f"[2025-02-16 16:22:08] Updated Git status by {vcutrone}: "
                f"branch={self.current_branch}, modified={len(modified_files)}, "
                f"staged={len(staged_files)}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:22:08] Error updating Git status: {str(e)}"
            )


    def handle_git_status_changed(self, status_info: Dict[str, Any]) -> None:
        """
        Handle Git status change events
        
        Last modified: 2025-02-16 16:22:53
        Modified by: vcutrone
        
        Args:
            status_info: Dictionary containing Git status information
        """
        try:
            # Update UI elements
            self.update_git_status()

            # Check for merge conflicts
            if status_info.get('merge_conflict'):
                self.handle_git_merge_conflict(status_info['conflicts'])

            # Handle branch tracking status
            ahead_count = status_info.get('ahead_count', 0)
            behind_count = status_info.get('behind_count', 0)

            if ahead_count > 0:
                self.show_status_message(
                    f"Your branch is ahead by {ahead_count} commit(s)",
                    warning=True
                )

            if behind_count > 0:
                self.show_status_message(
                    f"Your branch is behind by {behind_count} commit(s)",
                    warning=True
                )

            # Update file tree decorations
            self.file_tree.update_git_status(status_info)

            # Update branch menu if needed
            if status_info.get('branches_changed'):
                self.update_branch_menu()

            self.logger.debug(
                f"[2025-02-16 16:22:53] Git status changed by {vcutrone}: "
                f"ahead={ahead_count}, behind={behind_count}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:22:53] Error handling Git status change: {str(e)}"
            )


    def handle_git_commit(self, commit_info: Dict[str, Any]) -> None:
        """
        Handle Git commit creation event
        
        Args:
            commit_info: Dictionary containing commit information
        """
        try:
            # Extract commit information
            commit_hash = commit_info['hash']
            commit_message = commit_info['message']
            changed_files = commit_info.get('files', [])

            # Update editor states
            for editor in self.get_all_editors():
                if not editor.file_path:
                    continue

                relative_path = os.path.relpath(editor.file_path, self.project_root)
                if relative_path in changed_files:
                    editor.mark_committed(commit_hash)
                    editor.clear_git_decorations()

            # Update git status
            self.update_git_status()

            # Add commit to history view
            self.git_widget.add_commit_to_history(commit_info)

            # Show notification
            self.show_status_message(
                f"Created commit: {commit_hash[:7]} - {commit_message}"
            )

            self.logger.debug(
                f"[2025-02-16 16:22:53] Git commit created by {vcutrone}: "
                f"hash={commit_hash[:7]}, files={len(changed_files)}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:22:53] Error handling Git commit: {str(e)}"
            )


    def handle_git_push(self, push_info: Dict[str, Any]) -> None:
        """
        Handle Git push completion event
        
        Args:
            push_info: Dictionary containing push operation information
        """
        try:
            # Extract push information
            remote = push_info['remote']
            branch = push_info['branch']
            commit_count = push_info['commits']

            # Show progress dialog
            progress = QProgressDialog("Pushing commits...", "Cancel", 0, commit_count, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Update remote tracking
                self.update_remote_tracking(
                    remote,
                    branch,
                    progress_callback=lambda x: progress.setValue(x)
                )

                # Update status
                self.update_git_status()

                # Show success message
                self.show_status_message(
                    f"Pushed {commit_count} commit(s) to {remote}/{branch}"
                )

            finally:
                progress.close()

            self.logger.debug(
                f"[2025-02-16 16:22:53] Git push completed by {vcutrone}: "
                f"remote={remote}, branch={branch}, commits={commit_count}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:22:53] Error handling Git push: {str(e)}"
            )
            self.show_status_message("Push failed", error=True)


    def handle_git_pull(self, pull_info: Dict[str, Any]) -> None:
        """
        Handle Git pull completion event
        
        Last modified: 2025-02-16 16:23:38
        Modified by: vcutrone
        
        Args:
            pull_info: Dictionary containing pull operation information
        """
        try:
            # Extract pull information
            remote = pull_info['remote']
            branch = pull_info['branch']
            files_changed = pull_info.get('files_changed', [])
            insertions = pull_info.get('insertions', 0)
            deletions = pull_info.get('deletions', 0)

            # Show progress dialog
            progress = QProgressDialog("Updating workspace...", "Cancel", 0, len(files_changed), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Reload changed files
                for i, file_path in enumerate(files_changed):
                    progress.setValue(i)

                    # Update editor if file is open
                    editor = self.get_editor_by_path(file_path)
                    if editor:
                        editor.reload_content(preserve_undo=True)
                        editor.clear_git_decorations()

                # Update git status
                self.update_git_status()

                # Update history view
                self.git_widget.refresh_history()

                # Show success message
                self.show_status_message(
                    f"Pulled from {remote}/{branch}: "
                    f"{len(files_changed)} files changed, "
                    f"+{insertions} −{deletions}"
                )

            finally:
                progress.close()

            self.logger.debug(
                f"[2025-02-16 16:23:38] Git pull completed by {vcutrone}: "
                f"remote={remote}, branch={branch}, files={len(files_changed)}, "
                f"+{insertions} −{deletions}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:23:38] Error handling Git pull: {str(e)}"
            )
            self.show_status_message("Pull failed", error=True)


    def handle_git_merge_conflict(self, conflict_info: Dict[str, Any]) -> None:
        """
        Handle Git merge conflict event with visual merge tool
        
        Args:
            conflict_info: Dictionary containing conflict information
        """
        try:
            # Extract conflict information
            conflicted_files = conflict_info['files']
            current_branch = conflict_info['current_branch']
            other_branch = conflict_info['other_branch']

            # Create merge conflict dialog
            dialog = MergeConflictDialog(
                self,
                conflicted_files=conflicted_files,
                current_branch=current_branch,
                other_branch=other_branch,
                git_widget=self.git_widget
            )

            # Apply custom styling
            dialog.setStyleSheet(self._get_merge_dialog_style())

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Handle each conflicted file
                for file_path in conflicted_files:
                    self.open_merge_conflict_editor(file_path)
            else:
                # Abort merge
                self.git_widget.abort_merge()
                self.show_status_message("Merge aborted")
                self.update_git_status()

            self.logger.debug(
                f"[2025-02-16 16:23:38] Handling merge conflict by {vcutrone}: "
                f"files={len(conflicted_files)}, branches={current_branch}/{other_branch}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:23:38] Error handling merge conflict: {str(e)}"
            )
            self.show_status_message("Failed to handle merge conflict", error=True)


    def _get_merge_dialog_style(self) -> str:
        """Get custom styling for merge dialog"""
        return """
            QDialog {
                background-color: #2b2b2b;
                color: #d4d4d4;
            }
            QLabel {
                color: #d4d4d4;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QListWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            QListWidget::item:selected {
                background-color: #3c3c3c;
            }
        """


    def update_remote_tracking(self, remote: str, branch: str,
                               progress_callback: Optional[Callable[[int], None]] = None) -> None:
        """
        Update remote branch tracking information
        
        Args:
            remote: Remote name
            branch: Branch name
            progress_callback: Optional callback for progress updates
        """
        try:
            # Get remote branch information
            remote_info = self.git_widget.get_remote_info(
                remote,
                branch,
                progress_callback=progress_callback
            )

            if not remote_info:
                return

            # Update tracking status
            self.remote_branches[f"{remote}/{branch}"] = {
                'last_fetch': datetime.now(),
                'commit': remote_info['commit'],
                'ahead': remote_info['ahead'],
                'behind': remote_info['behind']
            }

            # Update branch status indicator if current branch
            if self.current_branch == branch:
                status_parts = [f"Git: {branch}"]

                if remote_info['ahead'] > 0:
                    status_parts.append(f"↑{remote_info['ahead']}")
                if remote_info['behind'] > 0:
                    status_parts.append(f"↓{remote_info['behind']}")

                self.git_status_label.setText(" ".join(status_parts))

            self.logger.debug(
                f"[2025-02-16 16:23:38] Updated remote tracking by {vcutrone}: "
                f"remote={remote}, branch={branch}, "
                f"ahead={remote_info['ahead']}, behind={remote_info['behind']}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:23:38] Error updating remote tracking: {str(e)}"
            )


    def pop_stash(self) -> bool:
        """
        Pop most recent stash and apply changes
        
        Last modified: 2025-02-16 16:26:55
        Modified by: vcutrone
        
        Returns:
            bool: True if stash was popped successfully
        """
        try:
            # Confirm stash pop with custom dialog
            response = QMessageBox(self)
            response.setWindowTitle("Pop Stash")
            response.setText("Pop and apply most recent stash?")
            response.setInformativeText("This will remove it from the stash list.")
            response.setStandardButtons(QMessageBox.StandardButton.Yes |
                                        QMessageBox.StandardButton.No)
            response.setIcon(QMessageBox.Icon.Question)

            if response.exec() != QMessageBox.StandardButton.Yes:
                return False

            # Show progress dialog
            progress = QProgressDialog("Applying stash...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Pop stash with progress updates
                result = self.git_widget.stash_pop(
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message("Stash applied and removed successfully")

                # Update UI
                self.update_git_status()
                self.update_stash_menu()
                self.refresh_workspace_files()

                # Reload affected editors
                if 'changed_files' in result:
                    self.reload_changed_editors(result['changed_files'])

                self.logger.debug(
                    f"[2025-02-16 16:26:55] Stash popped successfully by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Stash Pop Failed",
                    f"Failed to pop stash:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:26:55] Error popping stash: {str(e)}"
            )
            self.show_status_message("Failed to pop stash", error=True)
            return False


    def show_stash_apply_dialog(self) -> bool:
        """
        Show dialog for applying specific stash
        
        Returns:
            bool: True if stash was applied successfully
        """
        try:
            # Get stash list with details
            stash_list = self.git_widget.get_stash_list(include_diff=True)

            if not stash_list:
                QMessageBox.information(
                    self,
                    "Apply Stash",
                    "No stashes available to apply"
                )
                return False

            # Create and configure dialog
            dialog = StashSelectDialog(
                self,
                stash_list=stash_list,
                window_title="Apply Stash",
                show_keep_option=True
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            # Get dialog results
            stash_index = dialog.selected_stash
            keep_stash = dialog.keep_stash

            # Show progress dialog
            progress = QProgressDialog("Applying stash...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                # Apply selected stash
                result = self.git_widget.stash_apply(
                    stash_index,
                    keep=keep_stash,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Stash {stash_index} applied successfully")

                # Update UI
                self.update_git_status()
                if not keep_stash:
                    self.update_stash_menu()
                self.refresh_workspace_files()

                # Reload affected editors
                if 'changed_files' in result:
                    self.reload_changed_editors(result['changed_files'])

                self.logger.debug(
                    f"[2025-02-16 16:26:55] Stash {stash_index} applied by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Stash Apply Failed",
                    f"Failed to apply stash:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:26:55] Error showing stash apply dialog: {str(e)}"
            )
            return False


    def show_stash_list(self) -> None:
        """
        Show dialog displaying all stashed changes with details
        
        Last modified: 2025-02-16 16:27:27
        Modified by: vcutrone
        """
        try:
            # Get stash list with details and diffs
            progress = QProgressDialog("Loading stash details...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                stash_list = self.git_widget.get_stash_list(
                    include_diff=True,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if not stash_list:
                QMessageBox.information(
                    self,
                    "Stash List",
                    "No stashed changes found"
                )
                return

            # Create and configure stash list dialog
            dialog = StashListDialog(
                parent=self,
                stash_list=stash_list,
                git_widget=self.git_widget
            )

            # Connect signals
            dialog.stashDropped.connect(self.handle_stash_dropped)
            dialog.stashApplied.connect(self.handle_stash_applied)
            dialog.stashBranchCreated.connect(self.handle_branch_created)

            # Apply custom styling
            dialog.setStyleSheet(self._get_stash_dialog_style())

            dialog.exec()

            self.logger.debug(
                f"[2025-02-16 16:27:27] Showed stash list by {vcutrone}: "
                f"count={len(stash_list)}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:27:27] Error showing stash list: {str(e)}"
            )
            self.show_status_message("Failed to show stash list", error=True)


    def clear_stash(self) -> bool:
        """
        Clear all stashed changes
        
        Returns:
            bool: True if stash was cleared successfully
        """
        try:
            # Confirm stash clear with detailed dialog
            response = QMessageBox(self)
            response.setWindowTitle("Clear Stash")
            response.setText("Clear all stashed changes?")
            response.setInformativeText(
                "This will permanently delete all stashed changes. "
                "This action cannot be undone."
            )
            response.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            response.setIcon(QMessageBox.Icon.Warning)
            response.setDefaultButton(QMessageBox.StandardButton.No)

            if response.exec() != QMessageBox.StandardButton.Yes:
                return False

            # Clear stash with progress
            progress = QProgressDialog("Clearing stash...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                result = self.git_widget.stash_clear(
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message("Stash cleared successfully")
                self.update_stash_menu()

                self.logger.debug(
                    f"[2025-02-16 16:27:27] Stash cleared by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Clear Stash Failed",
                    f"Failed to clear stash:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:27:27] Error clearing stash: {str(e)}"
            )
            self.show_status_message("Failed to clear stash", error=True)
            return False


    def _get_stash_dialog_style(self) -> str:
        """Get custom styling for stash dialogs"""
        return """
            QDialog {
                background-color: #2b2b2b;
                color: #d4d4d4;
            }
            QListWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                selection-background-color: #3c3c3c;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: monospace;
            }
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
            QLabel {
                color: #d4d4d4;
            }
        """


    def handle_stash_dropped(self, stash_index: int) -> bool:
        """
        Handle stash drop event from stash list dialog
        
        Last modified: 2025-02-16 16:37:33
        Modified by: vcutrone
        
        Args:
            stash_index: Index of the stash to drop
            
        Returns:
            bool: True if stash was dropped successfully
        """
        try:
            # Show confirmation dialog
            response = QMessageBox(self)
            response.setWindowTitle("Drop Stash")
            response.setText(f"Drop stash {stash_index}?")
            response.setInformativeText("This action cannot be undone.")
            response.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            response.setIcon(QMessageBox.Icon.Warning)

            if response.exec() != QMessageBox.StandardButton.Yes:
                return False

            # Drop stash with progress
            progress = QProgressDialog("Dropping stash...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                result = self.git_widget.stash_drop(
                    stash_index,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Stash {stash_index} dropped successfully")
                self.update_stash_menu()

                self.logger.debug(
                    f"[2025-02-16 16:37:33] Stash {stash_index} dropped by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Drop Stash Failed",
                    f"Failed to drop stash {stash_index}:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:37:33] Error dropping stash: {str(e)}"
            )
            self.show_status_message("Failed to drop stash", error=True)
            return False


    def handle_stash_applied(self, stash_index: int, keep_stash: bool = True) -> bool:
        """
        Handle stash apply event from stash list dialog
        
        Args:
            stash_index: Index of the stash to apply
            keep_stash: Whether to keep the stash after applying
            
        Returns:
            bool: True if stash was applied successfully
        """
        try:
            # Show progress dialog
            progress = QProgressDialog("Applying stash...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                result = self.git_widget.stash_apply(
                    stash_index,
                    keep=keep_stash,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Stash {stash_index} applied successfully")

                # Update UI
                self.update_git_status()
                if not keep_stash:
                    self.update_stash_menu()
                self.refresh_workspace_files()

                # Reload affected editors
                if 'changed_files' in result:
                    self.reload_changed_editors(result['changed_files'])

                self.logger.debug(
                    f"[2025-02-16 16:37:33] Stash {stash_index} applied by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Apply Stash Failed",
                    f"Failed to apply stash {stash_index}:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:37:33] Error applying stash: {str(e)}"
            )
            self.show_status_message("Failed to apply stash", error=True)
            return False


    def setup_tag_menu(self) -> None:
        """Setup Git tag menu and actions with enhanced functionality"""
        try:
            # Create tag menu with custom styling
            self.tag_menu = QMenu("Tags", self)
            self.tag_menu.setStyleSheet(self._get_menu_style())
            self.git_menu.addMenu(self.tag_menu)

            # Add tag actions with icons
            actions = [
                ("Create Tag...", self.show_create_tag_dialog, "tag-add"),
                ("Delete Tag...", self.show_delete_tag_dialog, "tag-remove"),
                (None, None, None),  # Separator
                ("Push Tags...", self.show_push_tags_dialog, "tag-push"),
                ("Fetch Tags", self.fetch_tags, "tag-fetch"),
                (None, None, None),  # Separator
                ("Show Tag History", self.show_tag_history, "tag-history")
            ]

            for text, slot, icon_name in actions:
                if text is None:
                    self.tag_menu.addSeparator()
                    continue

                action = QAction(text, self)
                if icon_name:
                    action.setIcon(QIcon(f":/icons/{icon_name}.png"))
                action.triggered.connect(slot)
                self.tag_menu.addAction(action)

            # Update initial state
            self.update_tag_menu()

            self.logger.debug(
                f"[2025-02-16 16:37:33] Tag menu setup by {vcutrone}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:37:33] Error setting up tag menu: {str(e)}"
            )


    def update_tag_menu(self) -> None:
        """
        Update Git tag menu state and items
        
        Last modified: 2025-02-16 16:38:24
        Modified by: vcutrone
        """
        try:
            # Get tag list with details
            tags = self.git_widget.get_tags(include_messages=True)
            has_tags = bool(tags)

            # Update menu actions
            for action in self.tag_menu.actions():
                if action.text() in ["Delete Tag...", "Push Tags..."]:
                    action.setEnabled(has_tags)

            # Add recent tags submenu
            recent_tags_menu = self.tag_menu.findChild(QMenu, "recent_tags")
            if recent_tags_menu:
                self.tag_menu.removeAction(recent_tags_menu.menuAction())

            if has_tags:
                recent_tags_menu = QMenu("Recent Tags", self)
                recent_tags_menu.setObjectName("recent_tags")
                recent_tags_menu.setStyleSheet(self._get_menu_style())

                # Add most recent tags (up to 5)
                for tag in sorted(tags.items(), key=lambda x: x[1]['date'])[-5:]:
                    tag_name, tag_info = tag
                    action = recent_tags_menu.addAction(
                        f"{tag_name} ({tag_info['date'].strftime('%Y-%m-%d')})"
                    )
                    action.setData(tag_name)
                    action.triggered.connect(
                        lambda checked, t=tag_name: self.checkout_tag(t)
                    )

                self.tag_menu.insertMenu(self.tag_menu.actions()[0], recent_tags_menu)

            self.logger.debug(
                f"[2025-02-16 16:38:24] Updated tag menu by {vcutrone}: "
                f"tags={len(tags)}"
            )

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:38:24] Error updating tag menu: {str(e)}"
            )


    def show_create_tag_dialog(self) -> bool:
        """
        Show dialog for creating a new Git tag
        
        Returns:
            bool: True if tag was created successfully
        """
        try:
            # Create and configure dialog
            dialog = CreateTagDialog(
                parent=self,
                git_widget=self.git_widget,
                style_sheet=self._get_dialog_style()
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            # Get dialog data
            tag_data = {
                'name': dialog.tag_name,
                'message': dialog.tag_message,
                'commit': dialog.commit_hash,
                'sign': dialog.sign_tag,
                'force': dialog.force_tag
            }

            # Show progress dialog
            progress = QProgressDialog("Creating tag...", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            try:
                result = self.git_widget.create_tag(
                    **tag_data,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Created tag: {tag_data['name']}")
                self.update_tag_menu()

                # Offer to push tag
                if self.git_widget.has_remotes():
                    response = QMessageBox.question(
                        self,
                        "Push Tag",
                        f"Tag {tag_data['name']} created successfully. "
                        "Push to remote repository?",
                        QMessageBox.StandardButton.Yes |
                        QMessageBox.StandardButton.No
                    )

                    if response == QMessageBox.StandardButton.Yes:
                        self.push_tags([tag_data['name']])

                self.logger.debug(
                    f"[2025-02-16 16:38:24] Created tag {tag_data['name']} by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Tag Creation Failed",
                    f"Failed to create tag {tag_data['name']}:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:38:24] Error creating tag: {str(e)}"
            )
            self.show_status_message("Failed to create tag", error=True)
            return False


    def show_delete_tag_dialog(self) -> bool:
        """
        Show dialog for deleting Git tags
        
        Returns:
            bool: True if all selected tags were deleted successfully
        """
        try:
            # Get list of tags
            tags = self.git_widget.get_tags(include_messages=True)

            if not tags:
                QMessageBox.information(
                    self,
                    "Delete Tag",
                    "No tags available for deletion"
                )
                return False

            # Show tag selection dialog
            dialog = DeleteTagDialog(
                parent=self,
                tags=tags,
                git_widget=self.git_widget,
                style_sheet=self._get_dialog_style()
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            # Get selected tags and options
            selected_tags = dialog.selected_tags
            delete_remote = dialog.delete_remote
            force_delete = dialog.force_delete

            success_count = 0
            failed_tags = []

            # Show progress dialog
            progress = QProgressDialog(
                "Deleting tags...",
                "Cancel",
                0,
                len(selected_tags),
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                for i, tag in enumerate(selected_tags):
                    progress.setValue(i)
                    progress.setLabelText(f"Deleting tag: {tag}")

                    result = self.git_widget.delete_tag(
                        tag,
                        remote=delete_remote,
                        force=force_delete
                    )

                    if result['success']:
                        success_count += 1
                    else:
                        failed_tags.append((tag, result['error']))

            finally:
                progress.close()

            # Show results
            if failed_tags:
                error_msg = "\n".join(
                    f"{tag}: {error}" for tag, error in failed_tags
                )
                QMessageBox.warning(
                    self,
                    "Tag Deletion Results",
                    f"Successfully deleted {success_count} tag(s)\n"
                    f"Failed to delete {len(failed_tags)} tag(s):\n{error_msg}"
                )
            else:
                self.show_status_message(
                    f"Successfully deleted {success_count} tag(s)"
                )

            # Update UI
            self.update_tag_menu()

            self.logger.debug(
                f"[2025-02-16 16:38:24] Deleted tags by {vcutrone}: "
                f"success={success_count}, failed={len(failed_tags)}"
            )
            return success_count > 0

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:38:24] Error deleting tags: {str(e)}"
            )
            self.show_status_message("Failed to delete tags", error=True)
            return False


    def show_push_tags_dialog(self) -> bool:
        """
        Show dialog for pushing Git tags to remote
        
        Last modified: 2025-02-16 16:39:13
        Modified by: vcutrone
        
        Returns:
            bool: True if all selected tags were pushed successfully
        """
        try:
            # Get list of tags and remotes
            tags = self.git_widget.get_tags(include_messages=True)
            remotes = self.git_widget.get_remotes()

            # Validate requirements
            if not tags:
                QMessageBox.information(
                    self,
                    "Push Tags",
                    "No tags available to push"
                )
                return False

            if not remotes:
                QMessageBox.warning(
                    self,
                    "Push Tags",
                    "No remote repositories configured"
                )
                return False

            # Show tag push dialog
            dialog = PushTagsDialog(
                parent=self,
                tags=tags,
                remotes=remotes,
                git_widget=self.git_widget,
                style_sheet=self._get_dialog_style()
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            # Get selected options
            selected_tags = dialog.selected_tags
            selected_remote = dialog.selected_remote
            force_push = dialog.force_push

            # Show progress dialog
            progress = QProgressDialog(
                "Pushing tags...",
                "Cancel",
                0,
                len(selected_tags),
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                result = self.git_widget.push_tags(
                    selected_remote,
                    tags=selected_tags,
                    force=force_push,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(
                    f"Pushed {len(selected_tags)} tag(s) to {selected_remote}"
                )
                self.logger.debug(
                    f"[2025-02-16 16:39:13] Tags pushed by {vcutrone}: "
                    f"count={len(selected_tags)}, remote={selected_remote}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Push Tags Failed",
                    f"Failed to push tags:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:39:13] Error pushing tags: {str(e)}"
            )
            self.show_status_message("Failed to push tags", error=True)
            return False


    def _get_dialog_style(self) -> str:
        """Get custom styling for Git dialogs"""
        return """
            QDialog {
                background-color: #2b2b2b;
                color: #d4d4d4;
            }
            QLabel {
                color: #d4d4d4;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 5px;
                selection-background-color: #264f78;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(:/icons/dropdown.png);
            }
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
            QCheckBox {
                color: #d4d4d4;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                image: url(:/icons/checkbox-unchecked.png);
            }
            QCheckBox::indicator:checked {
                image: url(:/icons/checkbox-checked.png);
            }
        """


    def _get_menu_style(self) -> str:
        """Get custom styling for Git menus"""
        return """
            QMenu {
                background-color: #2b2b2b;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            QMenu::item {
                padding: 5px 20px 5px 24px;
            }
            QMenu::item:selected {
                background-color: #3c3c3c;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3c3c3c;
                margin: 4px 0px;
            }
            QMenu::indicator {
                width: 16px;
                height: 16px;
            }
        """


    def push_tags(self, tags: List[str], remote: Optional[str] = None) -> bool:
        """
        Push specified tags to remote repository
        
        Args:
            tags: List of tag names to push
            remote: Optional remote name (uses default if not specified)
            
        Returns:
            bool: True if tags were pushed successfully
        """
        try:
            if not remote:
                # Get default remote
                remotes = self.git_widget.get_remotes()
                if not remotes:
                    QMessageBox.warning(
                        self,
                        "Push Tags",
                        "No remote repositories configured"
                    )
                    return False

                remote = remotes[0]

            # Show progress dialog
            progress = QProgressDialog(
                f"Pushing tags to {remote}...",
                "Cancel",
                0,
                len(tags),
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                result = self.git_widget.push_tags(
                    remote,
                    tags=tags,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(
                    f"Pushed {len(tags)} tag(s) to {remote}"
                )
                self.logger.debug(
                    f"[2025-02-16 16:39:13] Tags pushed by {vcutrone}: "
                    f"count={len(tags)}, remote={remote}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Push Tags Failed",
                    f"Failed to push tags:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:39:13] Error pushing tags: {str(e)}"
            )
            self.show_status_message("Failed to push tags", error=True)
            return False


    from typing import List, Dict, Any, Optional
    from datetime import datetime
    import os
    import logging


    class GitMenuManager:
        """
        Manages Git-related menus and actions
        
        Last modified: 2025-02-16 16:41:31
        Modified by: vcutrone
        """

        def setup_stash_menu(self) -> None:
            """Setup Git stash menu with enhanced functionality"""
            try:
                # Create stash menu with styling
                self.stash_menu = QMenu("Stash", self)
                self.stash_menu.setStyleSheet(self._get_menu_style())
                self.git_menu.addMenu(self.stash_menu)

                # Define stash actions with icons
                stash_actions = [
                    ("Save Changes...", self.show_stash_save_dialog, "stash-save"),
                    ("Apply Stash...", self.show_stash_apply_dialog, "stash-apply"),
                    ("Pop Stash...", self.show_stash_pop_dialog, "stash-pop"),
                    (None, None, None),  # Separator
                    ("Drop Stash...", self.show_stash_drop_dialog, "stash-drop"),
                    ("Clear All Stashes", self.clear_all_stashes, "stash-clear")
                ]

                # Create actions with icons
                for text, slot, icon_name in stash_actions:
                    if text is None:
                        self.stash_menu.addSeparator()
                        continue

                    action = QAction(text, self)
                    if icon_name:
                        action.setIcon(QIcon(f":/icons/{icon_name}.png"))
                    action.triggered.connect(slot)
                    self.stash_menu.addAction(action)

                # Update initial state
                self.update_stash_menu()

                self.logger.debug(
                    f"[2025-02-16 16:41:31] Stash menu setup by {vcutrone}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 16:41:31] Error setting up stash menu: {str(e)}"
                )

        def update_stash_menu(self) -> None:
            """Update Git stash menu state based on current repository status"""
            try:
                # Get current state
                stashes = self.git_widget.get_stash_list()
                has_stashes = bool(stashes)
                has_changes = self.git_widget.has_uncommitted_changes()

                # Update action availability
                action_states = {
                    "Save Changes...": has_changes,
                    "Apply Stash...": has_stashes,
                    "Pop Stash...": has_stashes,
                    "Drop Stash...": has_stashes,
                    "Clear All Stashes": has_stashes
                }

                for action in self.stash_menu.actions():
                    if action.text() in action_states:
                        action.setEnabled(action_states[action.text()])

                # Update tooltips
                self._update_stash_tooltips(has_stashes, has_changes)

                self.logger.debug(
                    f"[2025-02-16 16:41:31] Updated stash menu by {vcutrone}: "
                    f"stashes={len(stashes)}, has_changes={has_changes}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 16:41:31] Error updating stash menu: {str(e)}"
                )

        def _update_stash_tooltips(self, has_stashes: bool, has_changes: bool) -> None:
            """Update tooltips for stash menu items"""
            tooltips = {
                "Save Changes...": "Save current changes to stash" if has_changes
                else "No changes to stash",
                "Apply Stash...": "Apply a stash to working directory" if has_stashes
                else "No stashes available",
                "Pop Stash...": "Apply and remove a stash" if has_stashes
                else "No stashes available",
                "Drop Stash...": "Delete a stash" if has_stashes
                else "No stashes available",
                "Clear All Stashes": f"Delete all stashes" if has_stashes
                else "No stashes available"
            }

            for action in self.stash_menu.actions():
                if action.text() in tooltips:
                    action.setToolTip(tooltips[action.text()])


    def show_stash_save_dialog(self) -> bool:
        """
        Show dialog for saving changes to Git stash
        
        Last modified: 2025-02-16 16:42:09
        Modified by: vcutrone
        
        Returns:
            bool: True if changes were stashed successfully
        """
        try:
            # Verify there are changes to stash
            if not self.git_widget.has_uncommitted_changes():
                QMessageBox.information(
                    self,
                    "Stash Save",
                    "No changes to stash"
                )
                return False

            # Create and configure dialog
            dialog = StashSaveDialog(
                parent=self,
                git_widget=self.git_widget,
                style_sheet=self._get_dialog_style()
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            # Get dialog data
            stash_data = {
                'message': dialog.stash_message,
                'include_untracked': dialog.include_untracked,
                'keep_index': dialog.keep_index
            }

            # Show progress dialog
            progress = QProgressDialog(
                "Saving changes to stash...",
                "Cancel",
                0,
                100,
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                result = self.git_widget.stash_save(
                    **stash_data,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message("Changes saved to stash")

                # Update UI
                self.update_stash_menu()
                self.refresh_workspace_files()

                self.logger.debug(
                    f"[2025-02-16 16:42:09] Changes stashed by {vcutrone}: "
                    f"message='{stash_data['message']}'"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Stash Save Failed",
                    f"Failed to save changes to stash:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:42:09] Error saving to stash: {str(e)}"
            )
            self.show_status_message("Failed to save changes to stash", error=True)
            return False


    def show_stash_apply_dialog(self) -> bool:
        """
        Show dialog for applying Git stash
        
        Returns:
            bool: True if stash was applied successfully
        """
        try:
            # Get stash list with details
            stashes = self.git_widget.get_stash_list(include_diff=True)

            if not stashes:
                QMessageBox.information(
                    self,
                    "Apply Stash",
                    "No stashes available"
                )
                return False

            # Create and configure dialog
            dialog = StashApplyDialog(
                parent=self,
                stashes=stashes,
                git_widget=self.git_widget,
                style_sheet=self._get_dialog_style()
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            # Get dialog data
            stash_ref = dialog.selected_stash
            restore_index = dialog.restore_index

            # Check for conflicts
            if self.git_widget.has_uncommitted_changes():
                response = QMessageBox.warning(
                    self,
                    "Apply Stash",
                    "You have uncommitted changes. Applying a stash may cause conflicts.\n"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if response != QMessageBox.StandardButton.Yes:
                    return False

            # Show progress dialog
            progress = QProgressDialog(
                "Applying stash...",
                "Cancel",
                0,
                100,
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                result = self.git_widget.stash_apply(
                    stash_ref,
                    restore_index=restore_index,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Applied stash {stash_ref}")

                # Update UI
                self.refresh_workspace_files()

                # Reload affected editors
                if 'changed_files' in result:
                    self.reload_changed_editors(result['changed_files'])

                self.logger.debug(
                    f"[2025-02-16 16:42:09] Stash {stash_ref} applied by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Apply Stash Failed",
                    f"Failed to apply stash:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:42:09] Error applying stash: {str(e)}"
            )
            self.show_status_message("Failed to apply stash", error=True)
            return False


    def show_stash_pop_dialog(self) -> bool:
        """
        Show dialog for popping Git stash
        
        Last modified: 2025-02-16 16:42:52
        Modified by: vcutrone
        
        Returns:
            bool: True if stash was popped successfully
        """
        try:
            # Get stash list with details
            stashes = self.git_widget.get_stash_list(include_diff=True)

            if not stashes:
                QMessageBox.information(
                    self,
                    "Pop Stash",
                    "No stashes available"
                )
                return False

            # Create and configure dialog
            dialog = StashPopDialog(
                parent=self,
                stashes=stashes,
                git_widget=self.git_widget,
                style_sheet=self._get_dialog_style()
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            # Get dialog data
            stash_ref = dialog.selected_stash
            restore_index = dialog.restore_index

            # Check for conflicts
            if self.git_widget.has_uncommitted_changes():
                response = QMessageBox.warning(
                    self,
                    "Pop Stash",
                    "You have uncommitted changes. Popping a stash may cause conflicts.\n"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if response != QMessageBox.StandardButton.Yes:
                    return False

            # Show progress dialog
            progress = QProgressDialog(
                "Popping stash...",
                "Cancel",
                0,
                100,
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                result = self.git_widget.stash_pop(
                    stash_ref,
                    restore_index=restore_index,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Popped stash {stash_ref}")

                # Update UI
                self.update_stash_menu()
                self.refresh_workspace_files()

                # Reload affected editors
                if 'changed_files' in result:
                    self.reload_changed_editors(result['changed_files'])

                self.logger.debug(
                    f"[2025-02-16 16:42:52] Stash {stash_ref} popped by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Pop Stash Failed",
                    f"Failed to pop stash:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:42:52] Error popping stash: {str(e)}"
            )
            self.show_status_message("Failed to pop stash", error=True)
            return False


    def show_stash_drop_dialog(self) -> bool:
        """
        Show dialog for dropping Git stash
        
        Returns:
            bool: True if stash was dropped successfully
        """
        try:
            # Get stash list with details
            stashes = self.git_widget.get_stash_list(include_diff=True)

            if not stashes:
                QMessageBox.information(
                    self,
                    "Drop Stash",
                    "No stashes available"
                )
                return False

            # Create and configure dialog
            dialog = StashDropDialog(
                parent=self,
                stashes=stashes,
                git_widget=self.git_widget,
                style_sheet=self._get_dialog_style()
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            stash_ref = dialog.selected_stash

            # Confirm stash drop
            response = QMessageBox.warning(
                self,
                "Drop Stash",
                f"Are you sure you want to drop stash {stash_ref}?\n"
                "This action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if response != QMessageBox.StandardButton.Yes:
                return False

            # Show progress dialog
            progress = QProgressDialog(
                "Dropping stash...",
                "Cancel",
                0,
                100,
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                result = self.git_widget.stash_drop(
                    stash_ref,
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Dropped stash {stash_ref}")
                self.update_stash_menu()

                self.logger.debug(
                    f"[2025-02-16 16:42:52] Stash {stash_ref} dropped by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Drop Stash Failed",
                    f"Failed to drop stash:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:42:52] Error dropping stash: {str(e)}"
            )
            self.show_status_message("Failed to drop stash", error=True)
            return False


    def clear_all_stashes(self) -> bool:
        """
        Clear all Git stashes
        
        Last modified: 2025-02-16 16:55:10
        Modified by: vcutrone
        
        Returns:
            bool: True if all stashes were cleared successfully
        """
        try:
            # Get stash list with details
            stashes = self.git_widget.get_stash_list(include_diff=True)

            if not stashes:
                QMessageBox.information(
                    self,
                    "Clear Stashes",
                    "No stashes available"
                )
                return False

            # Confirm clear operation
            response = QMessageBox.warning(
                self,
                "Clear All Stashes",
                f"Are you sure you want to clear all {len(stashes)} stashes?\n"
                "This action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if response != QMessageBox.StandardButton.Yes:
                return False

            # Show progress dialog
            progress = QProgressDialog(
                "Clearing all stashes...",
                "Cancel",
                0,
                100,
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            try:
                result = self.git_widget.clear_stashes(
                    progress_callback=lambda x: progress.setValue(x)
                )
            finally:
                progress.close()

            if result['success']:
                self.show_status_message(f"Cleared {len(stashes)} stashes")
                self.update_stash_menu()

                self.logger.debug(
                    f"[2025-02-16 16:55:10] {len(stashes)} stashes cleared by {vcutrone}"
                )
                return True

            else:
                QMessageBox.warning(
                    self,
                    "Clear Stashes Failed",
                    f"Failed to clear stashes:\n{result['error']}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:55:10] Error clearing stashes: {str(e)}"
            )
            self.show_status_message("Failed to clear stashes", error=True)
            return False


    def reload_changed_editors(self, changed_files: List[str]) -> None:
        """
        Reload editors for changed files
        
        Args:
            changed_files: List of file paths that have changed
        """
        try:
            for editor in self.get_all_editors():
                if not editor.file_path:
                    continue

                relative_path = os.path.relpath(
                    editor.file_path,
                    self.project_root
                )

                if relative_path in changed_files:
                    editor.reload_content(preserve_undo=True)
                    editor.clear_git_decorations()

        except Exception as e:
            self.logger.error(
                f"[2025-02-16 16:55:10] Error reloading editors: {str(e)}"
            )


    def _get_dialog_style(self) -> str:
        """Get custom styling for Git dialogs"""
        return """
            QDialog {
                background-color: #2b2b2b;
                color: #d4d4d4;
                min-width: 400px;
            }
            QLabel {
                color: #d4d4d4;
                padding: 5px;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 5px;
                selection-background-color: #264f78;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(:/icons/dropdown.png);
            }
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0d5789;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
            QCheckBox {
                color: #d4d4d4;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                image: url(:/icons/checkbox-unchecked.png);
            }
            QCheckBox::indicator:checked {
                image: url(:/icons/checkbox-checked.png);
            }
            QListWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #264f78;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 14px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #424242;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """


    def _get_menu_style(self) -> str:
        """
        Get custom styling for Git menus
        
        Last modified: 2025-02-16 16:55:52
        Modified by: vcutrone
        """
        return """
            QMenu {
                background-color: #2b2b2b;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 5px 0px;
            }
            QMenu::item {
                padding: 5px 20px 5px 24px;
            }
            QMenu::item:selected {
                background-color: #264f78;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3c3c3c;
                margin: 4px 0px;
            }
            QMenu::indicator {
                width: 16px;
                height: 16px;
                padding-left: 6px;
            }
            QMenu::icon {
                padding-left: 4px;
            }
        """


    class StashDialog(QDialog):
        """Base dialog class for Git stash operations"""

        def __init__(self, parent: Optional[QWidget] = None,
                     style_sheet: Optional[str] = None) -> None:
            super().__init__(parent)

            if style_sheet:
                self.setStyleSheet(style_sheet)

            self.setup_ui()
            self.setup_connections()

        def setup_ui(self) -> None:
            """Setup dialog UI components"""
            self.layout = QVBoxLayout(self)
            self.layout.setSpacing(10)
            self.layout.setContentsMargins(15, 15, 15, 15)

            # Add buttons
            self.button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok |
                QDialogButtonBox.StandardButton.Cancel
            )
            self.layout.addWidget(self.button_box)

        def setup_connections(self) -> None:
            """Setup signal connections"""
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)

        def validate(self) -> bool:
            """
            Validate dialog input
            
            Returns:
                bool: True if validation passes
            """
            return True

        def accept(self) -> None:
            """Handle dialog acceptance with validation"""
            if self.validate():
                super().accept()


    class StashSaveDialog(StashDialog):
        """Dialog for saving changes to stash"""

        def setup_ui(self) -> None:
            super().setup_ui()

            # Message input
            self.message_label = QLabel("Stash Message:", self)
            self.layout.addWidget(self.message_label)

            self.message_edit = QLineEdit(self)
            self.message_edit.setPlaceholderText("Enter a description for this stash")
            self.layout.addWidget(self.message_edit)

            # Options
            self.include_untracked = QCheckBox(
                "Include untracked files",
                self
            )
            self.layout.addWidget(self.include_untracked)

            self.keep_index = QCheckBox(
                "Keep staged changes",
                self
            )
            self.layout.addWidget(self.keep_index)

            self.layout.addWidget(self.button_box)

        @property
        def stash_message(self) -> str:
            """Get the stash message"""
            return self.message_edit.text().strip()

        def validate(self) -> bool:
            """Ensure message is not empty"""
            if not self.stash_message:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please enter a message for the stash"
                )
                return False
            return True


    def get_logger(name: str) -> logging.Logger:
        """
        Configure and get logger instance
        
        Args:
            name: Logger name
            
        Returns:
            logging.Logger: Configured logger instance
        """
        logger = logging.getLogger(name)

        if not logger.handlers:
            # Configure logging
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # File handler
            file_handler = logging.FileHandler('git_operations.log')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.INFO)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            logger.setLevel(logging.DEBUG)

        return logger


    # Initialize logger
    logger = get_logger(__name__)

    from typing import Dict, List, Optional, Any, Callable
    from datetime import datetime
    import os
    import logging
    from PyQt6.QtWidgets import (
        QMenu, QDialog, QMessageBox, QProgressDialog,
        QVBoxLayout, QLabel, QLineEdit, QCheckBox,
        QDialogButtonBox
    )
    from PyQt6.QtCore import Qt


    class GitManager:
        """
        Manages Git-related operations and UI interactions
        
        Last modified: 2025-02-16 16:58:48
        Modified by: vcutrone
        """

        def update_hook_menu(self) -> None:
            """Update Git hooks menu state"""
            try:
                # Get hook list with caching
                hooks = self._get_cached_hooks()
                has_hooks = bool(hooks)

                # Update action states
                action_states = {
                    "Edit Hook...": has_hooks,
                    "Remove Hook...": has_hooks,
                    "List Hooks": has_hooks
                }

                for action in self.hook_menu.actions():
                    if action.text() in action_states:
                        action.setEnabled(action_states[action.text()])

                # Update tooltips
                self._update_hook_tooltips(has_hooks)

                self.logger.debug(
                    f"[2025-02-16 16:58:48] Hook menu updated by {vcutrone}: "
                    f"hooks={len(hooks)}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 16:58:48] Error updating hook menu: {str(e)}"
                )

        def _get_cached_hooks(self) -> List[Dict[str, Any]]:
            """Get cached list of hooks or refresh cache"""
            if not hasattr(self, '_hooks_cache'):
                self._hooks_cache = self.git_widget.get_hooks()
            return self._hooks_cache

        def _update_hook_tooltips(self, has_hooks: bool) -> None:
            """Update tooltips for hook menu items"""
            tooltips = {
                "Edit Hook...": "Modify existing Git hook" if has_hooks
                else "No hooks available",
                "Remove Hook...": "Delete Git hook" if has_hooks
                else "No hooks available",
                "List Hooks": "Show all Git hooks" if has_hooks
                else "No hooks available"
            }

            for action in self.hook_menu.actions():
                if action.text() in tooltips:
                    action.setToolTip(tooltips[action.text()])

        def show_install_hook_dialog(self) -> bool:
            """
            Show dialog for installing Git hook
            
            Returns:
                bool: True if hook was installed successfully
            """
            try:
                # Get available hook types
                hook_types = self.git_widget.get_available_hook_types()

                # Create and configure dialog
                dialog = InstallHookDialog(
                    parent=self,
                    hook_types=hook_types,
                    git_widget=self.git_widget,
                    style_sheet=self._get_dialog_style()
                )

                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return False

                # Get dialog data
                hook_data = {
                    'type': dialog.hook_type,
                    'script': dialog.hook_script,
                    'executable': dialog.make_executable
                }

                # Validate script
                if not hook_data['script'].strip():
                    QMessageBox.warning(
                        self,
                        "Invalid Hook Script",
                        "Please provide a valid hook script"
                    )
                    return False

                # Check for existing hook
                if self.git_widget.hook_exists(hook_data['type']):
                    response = QMessageBox.warning(
                        self,
                        "Hook Exists",
                        f"A hook of type '{hook_data['type']}' already exists.\n"
                        "Do you want to overwrite it?",
                        QMessageBox.StandardButton.Yes |
                        QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if response != QMessageBox.StandardButton.Yes:
                        return False

                        # Show progress dialog
                progress = QProgressDialog(
                    f"Installing {hook_data['type']} hook...",
                    "Cancel",
                    0,
                    100,
                    self
                )
                progress.setWindowModality(Qt.WindowModality.WindowModal)

                try:
                    result = self.git_widget.install_hook(
                        **hook_data,
                        progress_callback=lambda x: progress.setValue(x)
                    )
                finally:
                    progress.close()

                if result['success']:
                    self.show_status_message(
                        f"Installed {hook_data['type']} hook"
                    )
                    # Update UI and cache
                    self._hooks_cache = None  # Force refresh
                    self.update_hook_menu()

                    self.logger.debug(
                        f"[2025-02-16 16:59:26] Hook installed by {vcutrone}: "
                        f"type={hook_data['type']}"
                    )
                    return True

                else:
                    QMessageBox.warning(
                        self,
                        "Install Hook Failed",
                        f"Failed to install hook:\n{result['error']}"
                    )
                    return False

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 16:59:26] Error installing hook: {str(e)}"
                )
                self.show_status_message("Failed to install hook", error=True)
                return False


    class HookDialog(QDialog):
        """Base dialog class for Git hook operations"""

        def __init__(self, parent: Optional[QWidget] = None,
                     style_sheet: Optional[str] = None) -> None:
            super().__init__(parent)

            if style_sheet:
                self.setStyleSheet(style_sheet)

            self.setup_ui()
            self.setup_connections()

        def setup_ui(self) -> None:
            """Setup dialog UI components"""
            self.setWindowTitle("Git Hook")
            self.setMinimumWidth(500)

            self.layout = QVBoxLayout(self)
            self.layout.setSpacing(10)
            self.layout.setContentsMargins(15, 15, 15, 15)

            # Add buttons
            self.button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok |
                QDialogButtonBox.StandardButton.Cancel
            )
            self.layout.addWidget(self.button_box)

        def setup_connections(self) -> None:
            """Setup signal connections"""
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)

        def validate(self) -> bool:
            """
            Validate dialog input
            
            Returns:
                bool: True if validation passes
            """
            return True

        def accept(self) -> None:
            """Handle dialog acceptance with validation"""
            if self.validate():
                super().accept()


    class InstallHookDialog(HookDialog):
        """Dialog for installing Git hook"""

        def __init__(self, parent: Optional[QWidget] = None,
                     hook_types: List[str] = None,
                     git_widget: Any = None,
                     style_sheet: Optional[str] = None) -> None:
            self.hook_types = hook_types or []
            self.git_widget = git_widget
            super().__init__(parent, style_sheet)

        def setup_ui(self) -> None:
            super().setup_ui()
            self.setWindowTitle("Install Git Hook")

            # Hook type selection
            self.type_label = QLabel("Hook Type:", self)
            self.layout.addWidget(self.type_label)

            self.type_combo = QComboBox(self)
            self.type_combo.addItems(self.hook_types)
            self.layout.addWidget(self.type_combo)

            # Script input
            self.script_label = QLabel("Hook Script:", self)
            self.layout.addWidget(self.script_label)

            self.script_edit = QPlainTextEdit(self)
            self.script_edit.setPlaceholderText("Enter hook script content")
            self.script_edit.setMinimumHeight(200)
            self.layout.addWidget(self.script_edit)

            # Options
            self.executable_check = QCheckBox(
                "Make script executable",
                self
            )
            self.executable_check.setChecked(True)
            self.layout.addWidget(self.executable_check)

            self.layout.addWidget(self.button_box)

        @property
        def hook_type(self) -> str:
            """Get selected hook type"""
            return self.type_combo.currentText()

        @property
        def hook_script(self) -> str:
            """Get hook script content"""
            return self.script_edit.toPlainText()

        @property
        def make_executable(self) -> bool:
            """Get executable flag"""
            return self.executable_check.isChecked()

        def validate(self) -> bool:
            """Validate dialog input"""
            if not self.hook_script.strip():
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please enter a hook script"
                )
                return False
            return True

        class EditHookDialog(HookDialog):
            """
            Dialog for editing Git hook

            Last modified: 2025-02-16 17:00:08
            Modified by: vcutrone
            """

        def __init__(self, parent: Optional[QWidget] = None,
                     hooks: Dict[str, Dict[str, Any]] = None,
                     git_widget: Any = None,
                     style_sheet: Optional[str] = None) -> None:
            self.hooks = hooks or {}
            self.git_widget = git_widget
            super().__init__(parent, style_sheet)

        def setup_ui(self) -> None:
            super().setup_ui()
            self.setWindowTitle("Edit Git Hook")

            # Hook selection
            self.hook_label = QLabel("Select Hook:", self)
            self.layout.addWidget(self.hook_label)

            self.hook_combo = QComboBox(self)
            self.hook_combo.addItems(sorted(self.hooks.keys()))
            self.hook_combo.currentTextChanged.connect(self._load_hook_script)
            self.layout.addWidget(self.hook_combo)

            # Script editor
            self.script_label = QLabel("Hook Script:", self)
            self.layout.addWidget(self.script_label)

            self.script_edit = QPlainTextEdit(self)
            self.script_edit.setMinimumHeight(200)
            self.layout.addWidget(self.script_edit)

            # Options
            self.executable_check = QCheckBox(
                "Make script executable",
                self
            )
            self.executable_check.setChecked(True)
            self.layout.addWidget(self.executable_check)

            self.layout.addWidget(self.button_box)

            # Load initial script
            if self.hooks:
                self._load_hook_script(self.hook_combo.currentText())

        def _load_hook_script(self, hook_type: str) -> None:
            """Load script content for selected hook"""
            try:
                if hook_type in self.hooks:
                    script = self.git_widget.get_hook_content(hook_type)
                    self.script_edit.setPlainText(script)

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 17:00:08] Error loading hook script: {str(e)}"
                )

        @property
        def selected_hook(self) -> str:
            """Get selected hook type"""
            return self.hook_combo.currentText()

        @property
        def hook_script(self) -> str:
            """Get hook script content"""
            return self.script_edit.toPlainText()

        @property
        def make_executable(self) -> bool:
            """Get executable flag"""
            return self.executable_check.isChecked()

        def validate(self) -> bool:
            """Validate dialog input"""
            if not self.hook_script.strip():
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please enter a hook script"
                )
                return False
            return True


    class RemoveHookDialog(HookDialog):
        """Dialog for removing Git hook"""

        def __init__(self, parent: Optional[QWidget] = None,
                     hooks: Dict[str, Dict[str, Any]] = None,
                     style_sheet: Optional[str] = None) -> None:
            self.hooks = hooks or {}
            super().__init__(parent, style_sheet)

        def setup_ui(self) -> None:
            super().setup_ui()
            self.setWindowTitle("Remove Git Hook")

            # Hook selection
            self.hook_label = QLabel(
                "Select hook to remove:",
                self
            )
            self.layout.addWidget(self.hook_label)

            self.hook_combo = QComboBox(self)
            self.hook_combo.addItems(sorted(self.hooks.keys()))
            self.layout.addWidget(self.hook_combo)

            # Warning label
            warning_text = (
                "Warning: This action cannot be undone. "
                "The hook script will be permanently deleted."
            )
            self.warning_label = QLabel(warning_text, self)
            self.warning_label.setStyleSheet("color: #ff6b6b;")
            self.warning_label.setWordWrap(True)
            self.layout.addWidget(self.warning_label)

            self.layout.addWidget(self.button_box)

        @property
        def selected_hook(self) -> str:
            """Get selected hook type"""
            return self.hook_combo.currentText()

        class ListHooksDialog(HookDialog):
            """
            Dialog for listing Git hooks
        
            Last modified: 2025-02-16 17:00:42
            Modified by: vcutrone
            """

        def __init__(self, parent: Optional[QWidget] = None,
                     hooks: Dict[str, Dict[str, Any]] = None,
                     style_sheet: Optional[str] = None) -> None:
            self.hooks = hooks or {}
            super().__init__(parent, style_sheet)

        def setup_ui(self) -> None:
            super().setup_ui()
            self.setWindowTitle("Git Hooks")
            self.setMinimumWidth(600)

            # Create hooks list
            self.hooks_list = QTableWidget(self)
            self.hooks_list.setColumnCount(4)
            self.hooks_list.setHorizontalHeaderLabels([
                "Hook Type",
                "Size",
                "Last Modified",
                "Executable"
            ])

            # Populate hooks list
            self.hooks_list.setRowCount(len(self.hooks))
            for row, (hook_type, info) in enumerate(sorted(self.hooks.items())):
                self.hooks_list.setItem(
                    row, 0, QTableWidgetItem(hook_type)
                )
                self.hooks_list.setItem(
                    row, 1, QTableWidgetItem(
                        self._format_size(info.get('size', 0))
                    )
                )
                self.hooks_list.setItem(
                    row, 2, QTableWidgetItem(
                        info.get('modified', '').strftime('%Y-%m-%d %H:%M:%S')
                    )
                )
                self.hooks_list.setItem(
                    row, 3, QTableWidgetItem(
                        "Yes" if info.get('executable', False) else "No"
                    )
                )

            # Adjust column widths
            self.hooks_list.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.Stretch
            )
            for col in range(1, 4):
                self.hooks_list.horizontalHeader().setSectionResizeMode(
                    col, QHeaderView.ResizeMode.ResizeToContents
                )

            self.layout.addWidget(self.hooks_list)

            # Add view button
            self.view_button = QPushButton("View Script", self)
            self.view_button.clicked.connect(self._view_hook_script)
            self.layout.addWidget(self.view_button)

            # Replace OK/Cancel with Close button
            self.button_box.clear()
            self.button_box.addButton(
                QDialogButtonBox.StandardButton.Close
            )

        def _format_size(self, size: int) -> str:
            """Format file size in human-readable format"""
            for unit in ['B', 'KB', 'MB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} GB"

        def _view_hook_script(self) -> None:
            """Show selected hook script content"""
            current_row = self.hooks_list.currentRow()
            if current_row >= 0:
                hook_type = self.hooks_list.item(current_row, 0).text()
                try:
                    script = self.git_widget.get_hook_content(hook_type)

                    dialog = QDialog(self)
                    dialog.setWindowTitle(f"Hook Script: {hook_type}")
                    dialog.setMinimumSize(700, 500)

                    layout = QVBoxLayout(dialog)

                    script_edit = QPlainTextEdit(dialog)
                    script_edit.setPlainText(script)
                    script_edit.setReadOnly(True)
                    layout.addWidget(script_edit)

                    button_box = QDialogButtonBox(
                        QDialogButtonBox.StandardButton.Close,
                        dialog
                    )
                    button_box.rejected.connect(dialog.reject)
                    layout.addWidget(button_box)

                    dialog.exec()

                except Exception as e:
                    self.logger.error(
                        f"[2025-02-16 17:00:42] Error viewing hook script: {str(e)}"
                    )
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Failed to load hook script:\n{str(e)}"
                    )


    class SubmoduleManager:
        """Manages Git submodule operations"""

        def __init__(self, parent: QWidget,
                     git_widget: Any,
                     logger: logging.Logger) -> None:
            self.parent = parent
            self.git_widget = git_widget
            self.logger = logger

        def setup_menu(self) -> QMenu:
            """Setup Git submodule menu"""
            try:
                menu = QMenu("Submodules", self.parent)

                # Add actions
                actions = [
                    ("Add Submodule...", self.show_add_dialog),
                    ("Update Submodules...", self.show_update_dialog),
                    ("Remove Submodule...", self.show_remove_dialog),
                    (None, None),  # Separator
                    ("List Submodules", self.show_list_dialog)
                ]

                for text, slot in actions:
                    if text is None:
                        menu.addSeparator()
                        continue

                    action = QAction(text, self.parent)
                    action.triggered.connect(slot)
                    menu.addAction(action)

                self.logger.debug(
                    f"[2025-02-16 17:00:42] Submodule menu setup by {vcutrone}"
                )

                return menu

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 17:00:42] Error setting up submodule menu: {str(e)}"
                )
                return QMenu(self.parent)

        class SubmoduleManager(GitBaseManager):
            """
            Manages Git submodule operations and UI
        
            Last modified: 2025-02-16 17:01:29
            Modified by: vcutrone
            """

        def update_menu_state(self, menu: QMenu) -> None:
            """Update submodule menu states"""
            try:
                submodules = self.git_widget.get_submodules()
                has_submodules = bool(submodules)

                # Update action states
                action_states = {
                    "Update Submodules...": has_submodules,
                    "Remove Submodule...": has_submodules,
                    "List Submodules": has_submodules
                }

                for action in menu.actions():
                    if action.text() in action_states:
                        action.setEnabled(action_states[action.text()])

                self.logger.debug(
                    f"[2025-02-16 17:01:29] Submodule menu updated by {vcutrone}: "
                    f"count={len(submodules)}"
                )

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 17:01:29] Error updating submodule menu: {str(e)}"
                )

        def show_add_dialog(self) -> bool:
            """Show dialog for adding submodule"""
            try:
                dialog = AddSubmoduleDialog(
                    parent=self.parent,
                    git_widget=self.git_widget,
                    style_sheet=self.get_dialog_style()
                )

                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return False

                # Get dialog data
                submodule_data = {
                    'repository': dialog.repository_url,
                    'path': dialog.submodule_path,
                    'branch': dialog.branch_name,
                    'shallow': dialog.shallow_clone,
                    'force': dialog.force_operation
                }

                # Validate repository URL
                if not self.git_widget.is_valid_repository_url(
                        submodule_data['repository']
                ):
                    QMessageBox.warning(
                        self.parent,
                        "Invalid Repository URL",
                        "Please provide a valid Git repository URL"
                    )
                    return False

                # Validate path
                if not submodule_data['path'] or submodule_data['path'].startswith('/'):
                    QMessageBox.warning(
                        self.parent,
                        "Invalid Path",
                        "Please provide a valid relative path for the submodule"
                    )
                    return False

                # Check if path exists
                full_path = os.path.join(
                    self.git_widget.repo_path,
                    submodule_data['path']
                )

                if os.path.exists(full_path) and not submodule_data['force']:
                    response = QMessageBox.warning(
                        self.parent,
                        "Path Exists",
                        f"The path '{submodule_data['path']}' already exists.\n"
                        "Do you want to force the operation?",
                        QMessageBox.StandardButton.Yes |
                        QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if response != QMessageBox.StandardButton.Yes:
                        return False
                    submodule_data['force'] = True

                # Show progress dialog
                progress = QProgressDialog(
                    f"Adding submodule {submodule_data['repository']}...",
                    "Cancel",
                    0,
                    100,
                    self.parent
                )
                progress.setWindowModality(Qt.WindowModality.WindowModal)

                try:
                    result = self.git_widget.add_submodule(
                        **submodule_data,
                        progress_callback=lambda x: progress.setValue(x)
                    )
                finally:
                    progress.close()

                if result['success']:
                    self.show_status_message(
                        f"Added submodule {submodule_data['repository']} "
                        f"at {submodule_data['path']}"
                    )
                    return True

                else:
                    QMessageBox.warning(
                        self.parent,
                        "Add Submodule Failed",
                        f"Failed to add submodule:\n{result['error']}"
                    )
                    return False

            except Exception as e:
                self.logger.error(
                    f"[2025-02-16 17:01:29] Error adding submodule: {str(e)}"
                )
                self.show_status_message("Failed to add submodule", error=True)
                return False

        def get_dialog_style(self) -> str:
            """Get custom styling for dialogs"""
            return """
                QDialog {
                    background-color: #2b2b2b;
                    color: #d4d4d4;
                }
                QLabel {
                    color: #d4d4d4;
                    padding: 5px;
                }
                QLineEdit, QTextEdit, QComboBox {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                    border-radius: 3px;
                    padding: 5px;
                }
                QPushButton {
                    background-color: #0e639c;
                    color: white;
                    border: none;
                    padding: 5px 15px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
                QPushButton:pressed {
                    background-color: #0d5789;
                }
                QPushButton:disabled {
                    background-color: #666666;
                }
                QTableWidget {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    gridline-color: #3c3c3c;
                    selection-background-color: #264f78;
                }
                QHeaderView::section {
                    background-color: #2b2b2b;
                    color: #d4d4d4;
                    padding: 5px;
                    border: none;
                }
            """


    # Initialize logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Add handlers if not already added
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler('git_operations.log')
        file_handler.setFormatter(
            logging.Formatter(
                '[%(asctime)s] %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        logger.addHandler(console_handler)
