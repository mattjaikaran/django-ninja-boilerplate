import pytest
from django.contrib.auth import get_user_model

from organizations.models import OrganizationMembership
from organizations.schemas import CreateOrganizationSchema, InviteMemberSchema
from organizations.services import OrganizationService

User = get_user_model()


@pytest.fixture
def service():
    return OrganizationService()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass123",
    )


@pytest.fixture
def second_user(db):
    return User.objects.create_user(
        username="seconduser",
        email="seconduser@example.com",
        password="testpass123",
    )


@pytest.fixture
def org(service, user):
    data = CreateOrganizationSchema(name="Test Org", slug="test-org")
    return service.create_organization(user, data)


@pytest.mark.django_db
class TestCreateOrganization:
    def test_creates_organization(self, service, user):
        data = CreateOrganizationSchema(name="My Org", slug="my-org")
        org = service.create_organization(user, data)

        assert org.name == "My Org"
        assert org.slug == "my-org"
        assert org.owner == user
        assert org.is_active is True

    def test_creates_owner_membership(self, service, user):
        data = CreateOrganizationSchema(name="My Org", slug="my-org")
        org = service.create_organization(user, data)

        membership = OrganizationMembership.objects.get(organization=org, user=user)
        assert membership.role == "owner"
        assert membership.is_active is True

    def test_auto_generates_slug_from_name(self, service, user):
        data = CreateOrganizationSchema(name="Auto Slug Org")
        org = service.create_organization(user, data)

        assert org.slug == "auto-slug-org"

    def test_slug_deduplication(self, service, user):
        data1 = CreateOrganizationSchema(name="Same Org")
        data2 = CreateOrganizationSchema(name="Same Org")
        org1 = service.create_organization(user, data1)
        org2 = service.create_organization(user, data2)

        assert org1.slug != org2.slug
        assert org2.slug == "same-org-1"


@pytest.mark.django_db
class TestListOrganizations:
    def test_user_sees_their_orgs(self, service, user, second_user):
        data1 = CreateOrganizationSchema(name="Org One", slug="org-one")
        data2 = CreateOrganizationSchema(name="Org Two", slug="org-two")
        data3 = CreateOrganizationSchema(name="Other Org", slug="other-org")

        service.create_organization(user, data1)
        service.create_organization(user, data2)
        service.create_organization(second_user, data3)

        orgs = list(service.list_organizations(user))
        assert len(orgs) == 2
        names = {o.name for o in orgs}
        assert "Org One" in names
        assert "Org Two" in names
        assert "Other Org" not in names

    def test_user_sees_orgs_invited_to(self, service, user, second_user):
        data = CreateOrganizationSchema(name="Shared Org", slug="shared-org")
        org = service.create_organization(user, data)

        invite_data = InviteMemberSchema(user_id=str(second_user.id), role="member")
        service.invite_member(str(org.id), user, invite_data)

        orgs = list(service.list_organizations(second_user))
        assert len(orgs) == 1
        assert orgs[0].id == org.id

    def test_inactive_orgs_not_shown(self, service, user):
        data = CreateOrganizationSchema(name="Dead Org", slug="dead-org")
        org = service.create_organization(user, data)
        org.is_active = False
        org.save()

        orgs = list(service.list_organizations(user))
        assert len(orgs) == 0


@pytest.mark.django_db
class TestInviteMember:
    def test_owner_can_invite_member(self, service, user, second_user, org):
        invite_data = InviteMemberSchema(user_id=str(second_user.id), role="member")
        membership = service.invite_member(str(org.id), user, invite_data)

        assert membership.user == second_user
        assert membership.role == "member"
        assert membership.is_active is True
        assert membership.invited_by == user

    def test_non_admin_cannot_invite(self, service, user, second_user, org):
        from ninja.errors import HttpError

        invite_data = InviteMemberSchema(user_id=str(second_user.id), role="member")
        service.invite_member(str(org.id), user, invite_data)

        third_user = User.objects.create_user(
            username="thirduser",
            email="thirduser@example.com",
            password="testpass123",
        )
        invite_third = InviteMemberSchema(user_id=str(third_user.id), role="member")

        with pytest.raises(HttpError) as exc_info:
            service.invite_member(str(org.id), second_user, invite_third)
        assert exc_info.value.status_code == 403

    def test_duplicate_invite_raises_conflict(self, service, user, second_user, org):
        from ninja.errors import HttpError

        invite_data = InviteMemberSchema(user_id=str(second_user.id), role="member")
        service.invite_member(str(org.id), user, invite_data)

        with pytest.raises(HttpError) as exc_info:
            service.invite_member(str(org.id), user, invite_data)
        assert exc_info.value.status_code == 409


@pytest.mark.django_db
class TestLeaveOrganization:
    def test_member_can_leave(self, service, user, second_user, org):
        invite_data = InviteMemberSchema(user_id=str(second_user.id), role="member")
        service.invite_member(str(org.id), user, invite_data)

        service.leave_organization(str(org.id), second_user)

        membership = OrganizationMembership.objects.get(
            organization=org, user=second_user
        )
        assert membership.is_active is False

    def test_last_owner_cannot_leave(self, service, user, org):
        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            service.leave_organization(str(org.id), user)
        assert exc_info.value.status_code == 400

    def test_owner_can_leave_if_another_owner_exists(
        self, service, user, second_user, org
    ):
        invite_data = InviteMemberSchema(user_id=str(second_user.id), role="owner")
        service.invite_member(str(org.id), user, invite_data)

        service.leave_organization(str(org.id), user)

        membership = OrganizationMembership.objects.get(organization=org, user=user)
        assert membership.is_active is False
