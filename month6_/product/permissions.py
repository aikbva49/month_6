from rest_framework import permissions

class IsModerator(permissions.BasePermission):
    def has_permission(self, request, view):

        if not (request.user and request.user.is_authenticated and request.user.is_staff):
            return False
        
        if request.method == 'POST':
            return False

        return True