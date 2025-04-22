from functools import wraps

from uipath.tracing._traced import TracingManager, traced


# Custom wrapper that does nothing
def donothing_custom_tracer(**kwargs):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Simple implementation that just adds a marker to the result
            result = func(*args, **kwargs)
            return result

        return wrapper

    return decorator


# Helper function for testing custom tracer
def simple_custom_tracer(**kwargs):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Simple implementation that just adds a marker to the result
            result = func(*args, **kwargs)
            if isinstance(result, dict):
                result["custom_tracer_used"] = True
            return result

        return wrapper

    return decorator


# Helper function for testing custom tracer with method
def custom_method_tracer(**kwargs):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if isinstance(result, dict):
                result["custom_method_tracer_used"] = True
            return result

        return wrapper

    return decorator


# Helper function for testing with counter
def custom_tracer_with_counter(call_counter, **kwargs):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            call_counter["count"] += 1
            result = func(*args, **kwargs)
            if isinstance(result, dict):
                result["custom_tracer_id"] = call_counter["count"]
            return result

        return wrapper

    return decorator


# Define the test classes
class TestClassForMethodTest:
    @traced()
    def sample_method(self, x, y):
        return {"product": x * y}


# Module level functions for function test
@traced()
def func1_for_test(x):
    return {"result": x * 2}


@traced()
def func2_for_test(x):
    return {"result": x * 3}


# Define a function with @traced
@traced()
def sample_function():
    return {"status": "success"}


def test_tracing_manager_custom_implementation():
    """Test setting and getting a custom tracer implementation."""
    # Set the custom implementation
    TracingManager.reapply_traced_decorator(simple_custom_tracer)

    # Get the implementation and verify it's the same one
    impl = TracingManager.get_custom_tracer_implementation()
    assert impl is simple_custom_tracer


def test_traced_with_custom_implementation():
    """Test that @traced uses a custom implementation when provided."""
    # Set the custom implementation
    TracingManager.reapply_traced_decorator(simple_custom_tracer)

    # Call the function and verify the custom implementation was used
    result = sample_function()
    assert "custom_tracer_used" in result
    assert result["custom_tracer_used"] is True


def test_reapply_traced_decorator_to_class_method():
    """Test reapply_traced_decorator with class methods."""
    TracingManager.reapply_traced_decorator(donothing_custom_tracer)

    # Create instance and call with default implementation
    instance = TestClassForMethodTest()
    result1 = instance.sample_method(2, 3)
    assert result1 == {"product": 6}

    # Apply our custom implementation
    TracingManager.reapply_traced_decorator(custom_method_tracer)

    # Create a NEW instance which will use the updated class method
    new_instance = TestClassForMethodTest()
    result2 = new_instance.sample_method(2, 3)

    # Verify the result
    assert "product" in result2
    assert result2["product"] == 6
    assert "custom_method_tracer_used" in result2


def test_reapply_to_module_level_functions():
    """Test reapply_traced_decorator with module level functions."""

    TracingManager.reapply_traced_decorator(donothing_custom_tracer)

    # First call with default implementation
    assert func1_for_test(5) == {"result": 10}
    assert func2_for_test(5) == {"result": 15}

    # Counter to track custom tracer calls
    call_counter = {"count": 0}

    # Reapply with the custom implementation
    TracingManager.reapply_traced_decorator(
        lambda **kwargs: custom_tracer_with_counter(call_counter, **kwargs)
    )

    # Call the functions directly - they should now use the updated implementation
    result1 = func1_for_test(5)
    result2 = func2_for_test(5)

    # Verify the custom implementation was applied
    assert "result" in result1
    assert result1["result"] == 10
    assert "custom_tracer_id" in result1

    assert "result" in result2
    assert result2["result"] == 15
    assert "custom_tracer_id" in result2

    # Verify both functions were processed
    assert call_counter["count"] == 2
