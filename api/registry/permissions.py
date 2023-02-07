from ninja_extra import permissions

class ResearcherPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name="Researcher").exists()
