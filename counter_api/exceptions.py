class CounterAPIError(Exception):
    def __init__(self, code, message, status_code, data=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data

        super().__init__(message)

    def as_dict(self):
        payload = {
            "Code": self.code,
            "Message": self.message,
        }
        if self.data:
            payload["Data"] = self.data
        return payload


def invalid_dates(data=None):
    return CounterAPIError(3020, "Invalid Date Arguments", 400, data)


def insufficient_information(data=None):
    return CounterAPIError(
        1030,
        "Insufficient Information to Process Request",
        400,
        data,
    )


def service_unavailable(data=None):
    return CounterAPIError(1000, "Service Not Available", 503, data)


def invalid_filter(data=None):
    return CounterAPIError(3060, "Invalid ReportFilter Value", 400, data)


def incongruous_filter(data=None):
    return CounterAPIError(3061, "Incongruous ReportFilter Value", 400, data)
