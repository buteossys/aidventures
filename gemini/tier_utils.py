import logging
from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse # Or another response for restriction
from functools import wraps

# Assuming your models are in 'your_app.models'
# Adjust the import path as necessary
# It's often better to pass QuerySets/objects rather than importing models
# directly into utils, but this works for demonstration.
from user_profile.models import UserProfile 
from gemini.models import Story, Adventure

logger = logging.getLogger(__name__)

# --- Tier Constants ---
TIER_FREE = 'free'
TIER_DAILY = 'daily'
TIER_FAMILY = 'family'
TIER_UNLIMITED = 'unlimited'

# --- Limit Constants ---
FREE_TIER_LIMIT = 10  # per month
DAILY_TIER_LIMIT = 7  # per week
FAMILY_TIER_LIMIT = 21  # per week
WEEK_DAYS = 7
MONTH_DAYS = 30  # Using 30 days as a standard month

# --- Tier-Specific Check Functions ---

def check_free_tier_limit(user_profile: UserProfile, story_instance=None) -> bool:
    """
    Checks if a 'free' tier user is within their monthly story limit.
    Month is calculated from user creation date.
    Updates story status to 'failed' if limit is reached.
    """
    try:
        now = timezone.now()
        user_created_at = user_profile.created_at

        if timezone.is_naive(user_created_at):
            user_created_at = timezone.make_aware(user_created_at, timezone.get_default_timezone())

        # Calculate months since creation
        delta_days = (now - user_created_at).days
        months_passed = delta_days // MONTH_DAYS

        # Calculate current month window
        current_month_start = user_created_at + timedelta(days=months_passed * MONTH_DAYS)
        current_month_end = current_month_start + timedelta(days=MONTH_DAYS)

        # Count stories in current month
        stories_this_month = Story.objects.filter(
            adventure__user=user_profile.user,
            created_at__gte=current_month_start,
            created_at__lt=current_month_end
        ).count()

        is_allowed = stories_this_month < FREE_TIER_LIMIT
        if not is_allowed:
            logger.info(f"Free tier user {user_profile.user.username} reached monthly limit ({stories_this_month}/{FREE_TIER_LIMIT}).")
            if story_instance:
                story_instance.status = 'failed'
                story_instance.save(update_fields=['status'])
                logger.info(f"Updated story {story_instance.id} status to failed due to free tier limit.")
        return is_allowed

    except Exception as e:
        logger.error(f"Error checking free tier limit for user {user_profile.user.username}: {e}", exc_info=True)
        if story_instance:
            story_instance.status = 'failed'
            story_instance.save(update_fields=['status'])
        return False

def check_subscription_tier_limit(user_profile: UserProfile, limit: int, story_instance=None) -> bool:
    """
    Checks if a subscription tier user is within their daily story limit.
    Updates story status to 'failed' if limit is reached.
    """
    try:
        today = timezone.now().date()
        
        # Count stories created today
        stories_today = Story.objects.filter(
            adventure__user=user_profile.user,
            created_at__date=today
        ).count()

        is_allowed = stories_today < limit
        if not is_allowed:
            logger.info(f"Subscription tier user {user_profile.user.username} reached daily limit ({stories_today}/{limit}).")
            if story_instance:
                story_instance.status = 'failed'
                story_instance.save(update_fields=['status'])
                logger.info(f"Updated story {story_instance.id} status to failed due to subscription tier limit.")
        return is_allowed

    except Exception as e:
        logger.error(f"Error checking subscription tier limit for user {user_profile.user.username}: {e}", exc_info=True)
        if story_instance:
            story_instance.status = 'failed'
            story_instance.save(update_fields=['status'])
        return False

# --- Main Check Function ---

def can_user_access_feature(user_profile: UserProfile) -> bool:
    """
    Determines if the user can access the restricted feature based on their tier and usage.
    """
    if not user_profile:
        logger.warning("Attempted access check without a user profile.")
        return False

    tier = user_profile.tier

    if tier == TIER_UNLIMITED:
        logger.debug(f"User {user_profile.user.username} has unrestricted access (Unlimited tier).")
        return True
    elif tier == TIER_FREE:
        return check_free_tier_limit(user_profile)
    elif tier == TIER_DAILY:
        return check_subscription_tier_limit(user_profile, DAILY_TIER_LIMIT)
    elif tier == TIER_FAMILY:
        return check_subscription_tier_limit(user_profile, FAMILY_TIER_LIMIT)
    else:
        logger.warning(f"User {user_profile.user.username} has unknown tier '{tier}'. Denying access.")
        return False


# --- Decorator for Views (Optional but recommended) ---

def check_access(view_func):
    """
    Decorator for regular Django views that need access checking.
    """
    @wraps(view_func)
    def _wrapped_view(request, adventure_id, *args, **kwargs):
        try:
            # Get the adventure and associated user
            adventure = Adventure.objects.get(id=adventure_id)
            user = adventure.user
            
            try:
                # Change from userprofile to profile
                user_profile = user.profile
            except UserProfile.DoesNotExist:
                logger.error(f"User {user.username} does not have a UserProfile. Denying access.")
                return JsonResponse({
                    'status': 'error',
                    'message': 'User profile not found'
                }, status=403)
            except AttributeError:
                logger.error(f"User object {user} has no 'profile' attribute.")
                return JsonResponse({
                    'status': 'error',
                    'message': 'User profile configuration error'
                }, status=403)

            # Perform the actual check
            if can_user_access_feature(user_profile):
                return view_func(request, adventure_id, *args, **kwargs)
            else:
                logger.warning(f"Access denied for user {user.username} based on tier limits.")
                return JsonResponse({
                    'status': 'error',
                    'message': 'You have reached your usage limit for this feature'
                }, status=403)

        except Adventure.DoesNotExist:
            logger.error(f"Adventure {adventure_id} not found")
            return JsonResponse({
                'status': 'error',
                'message': 'Adventure not found'
            }, status=404)

    return _wrapped_view

def thread_check_access(view_func):
    """
    Decorator specifically for threaded contexts that need access checking.
    Does not require authentication as that should be handled before thread creation.
    """
    @wraps(view_func)
    def _wrapped_view(adventure_id, *args, **kwargs):
        try:
            # Get the adventure and associated user
            adventure = Adventure.objects.get(id=adventure_id)
            user = adventure.user
            
            try:
                user_profile = user.profile
            except UserProfile.DoesNotExist:
                logger.error(f"User {user.username} does not have a UserProfile. Denying access.")
                return {
                    'status': 'error',
                    'message': 'User profile not found'
                }
            except AttributeError:
                logger.error(f"User object {user} has no 'profile' attribute.")
                return {
                    'status': 'error',
                    'message': 'User profile configuration error'
                }

            # Perform the actual check
            if can_user_access_feature(user_profile):
                return view_func(adventure_id, *args, **kwargs)
            else:
                logger.warning(f"Access denied for user {user.username} based on tier limits.")
                return {
                    'status': 'error',
                    'message': 'You have reached your usage limit for this feature'
                }

        except Adventure.DoesNotExist:
            logger.error(f"Adventure {adventure_id} not found")
            return {
                'status': 'error',
                'message': 'Adventure not found'
            }

    return _wrapped_view