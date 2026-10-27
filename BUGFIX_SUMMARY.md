# Bug Fix Summary: LMCache Query Engine Fallback Logic

## Bug Description
The LMCache query engine incorrectly falls back from `/v1/completions` to `/v1/chat/completions` after every RuntimeError, not only when the completions endpoint is unsupported or when there's a "missing chat template" error.

## Root Cause
In `/home/sach/LMCache/lmcache/cli/commands/query/_request.py`, the `_query_with_fallback` method had inconsistent logic:

1. **When `chat_first=True`**: It correctly only falls back to completions if the error is a "missing chat template" error (lines 343-348).

2. **When `chat_first=False` (default)**: It incorrectly falls back to chat completions for ANY RuntimeError from completions (line 349), without checking if it's a "missing chat template" error.

## The Fix
Added a check for `_missing_chat_template(first_err)` before falling back to chat completions, similar to the check done for the `chat_first=True` case.

### Before (lines 349-351):
```python
_info("/v1/completions failed; retrying with /v1/chat/completions")
try:
    return self._query(request_data, chat=True)
```

### After (lines 349-351):
```python
# FIX: Only fall back to chat completions if the first error is a missing chat template error
if not _missing_chat_template(first_err):
    raise
_info("/v1/completions failed; retrying with /v1/chat/completions")
try:
    return self._query(request_data, chat=True)
```

## Why This Fix Is Correct
1. **Consistency**: Both `chat_first=True` and `chat_first=False` now use the same `_missing_chat_template(first_err)` check to determine if a fallback is appropriate.

2. **Safety**: The fallback to chat completions should only happen when completions is failing due to a "missing chat template" error, not for ANY RuntimeError.

3. **User Experience**: Users will get a clearer error message when their model truly doesn't support either endpoint, rather than having their request silently fail to an inappropriate endpoint.

## Impact
This fix ensures that:
1. Users get appropriate error messages when their model truly doesn't support the requested endpoint
2. The query engine doesn't make unnecessary or inappropriate API calls
3. The behavior is consistent between `chat_first=True` and `chat_first=False` modes
4. The existing error handling logic for `chat_first=True` is preserved

## Testing
The fix has been thoroughly tested with the following scenarios:
1. ✓ Regular errors when `chat_first=False` do NOT fall back to chat completions
2. ✓ Missing chat template errors when `chat_first=False` DO fall back to chat completions
3. ✓ Regular errors when `chat_first=True` do NOT fall back to completions
4. ✓ Missing chat template errors when `chat_first=True` DO fall back to completions
5. ✓ `completions_only=True` only tries completions

## Files Modified
- `/home/sach/LMCache/lmcache/cli/commands/query/_request.py` (lines 349-350 added)

## Verification
The fix maintains backward compatibility for all existing use cases while fixing the bug where regular errors incorrectly triggered a fallback to the inappropriate endpoint.

The behavior is now:
- **Before**: All RuntimeErrors from completions triggered fallback to chat completions
- **After**: Only "missing chat template" errors from completions trigger fallback to chat completions

This aligns with the original design intent where the fallback was meant to handle the specific case of models that only support chat completion format (with a chat template) but not the older completions endpoint format.
