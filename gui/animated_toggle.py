"""Animated toggle switch for PyQt6 based on QToggle implementation."""

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import pyqtSignal, QEasingCurve, QPropertyAnimation, QRect, Qt, pyqtProperty, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFontMetrics


class AnimatedToggle(QWidget):
    """Animated toggle switch widget with smooth transition animation."""
    
    stateChanged = pyqtSignal(bool)  # Signal emitted when toggle state changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 24)
        self._checked = False
        self._position = 0  # 0 for left (off), 1 for right (on)
        self._track_color = QColor("#424242")
        self._thumb_color = QColor("white")
        self._checked_track_color = QColor("#8c62ff")
        
        # Animation for smooth transition
        self._animation = QPropertyAnimation(self, b"position")
        self._animation.setDuration(200)  # 200ms animation
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._animation.finished.connect(self._on_animation_finished)
        
        # Enable mouse tracking
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def _on_animation_finished(self):
        """Handle animation finished event."""
        # Emit state changed signal only when animation completes
        self.stateChanged.emit(self._checked)
    
    def isChecked(self):
        """Return the current checked state."""
        return self._checked
    
    def setChecked(self, checked):
        """Set the checked state with animation."""
        if self._checked != checked:
            self._checked = checked
            # Start animation
            start_pos = self._position
            end_pos = 1.0 if checked else 0.0
            self._animation.setStartValue(start_pos)
            self._animation.setEndValue(end_pos)
            self._animation.start()
            # Update immediately for visual feedback
            self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse press event to toggle state."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)
    
    def paintEvent(self, event):
        """Paint the toggle switch."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw track
        track_rect = QRect(2, 2, self.width() - 4, self.height() - 4)
        track_radius = track_rect.height() // 2
        
        # Choose track color based on state
        if self._checked:
            track_color = self._checked_track_color
        else:
            track_color = self._track_color
            
        painter.setBrush(track_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, track_radius, track_radius)
        
        # Draw thumb with animation position
        thumb_size = self.height() - 8
        thumb_radius = thumb_size // 2
        thumb_x = int(4 + (self.width() - thumb_size - 8) * self._position)
        thumb_y = 4
        thumb_rect = QRect(thumb_x, thumb_y, thumb_size, thumb_size)
        
        painter.setBrush(self._thumb_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(thumb_rect)
    
    def getPosition(self):
        """Get the current animation position (0.0 to 1.0)."""
        return self._position
    
    def setPosition(self, position):
        """Set the animation position and update display."""
        self._position = position
        self.update()
    
    # Define position as a Qt property for animation
    position = pyqtProperty(float, getPosition, setPosition)


if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # Create a simple test window
    window = QWidget()
    window.setWindowTitle("Animated Toggle Test")
    window.setGeometry(100, 100, 300, 200)
    
    toggle = AnimatedToggle(window)
    toggle.move(50, 50)
    
    def on_state_changed(state):
        print(f"Toggle state changed to: {state}")
    
    toggle.stateChanged.connect(on_state_changed)
    
    window.show()
    sys.exit(app.exec())