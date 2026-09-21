class CyToolError(Exception):
    def __init__(self, code, message, *, details=None, recoverable=False, suggested_action=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.recoverable = recoverable
        self.suggested_action = suggested_action

    def to_dict(self):
        return {"code": self.code, "message": self.message,
                "technicalDetails": self.details, "recoverable": self.recoverable,
                "suggestedAction": self.suggested_action}
