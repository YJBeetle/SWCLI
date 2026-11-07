"""Modern GetSystemValue3 stand-ins for existing geometry fault fixtures."""

def single_configuration_values(observer):
    # Mock.side_effect also accepts exception instances; retain that contract.
    if not callable(observer):
        return observer
    def read(which, name):
        if type(which) is not int or which != 3 or not isinstance(name, str) or not name.strip():
            raise AssertionError("expected swSpecifyConfiguration and exactly one named configuration")
        return (observer(name),)
    return read
