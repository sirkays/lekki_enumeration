from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
    parser_classes
)

from rest_framework_api_key.permissions import HasAPIKey
from authapp.authentication import SessionTokenAuthentication
from .models import SessionToken, UserProfile
from .serializers import CurrentUserSerializer

User = get_user_model()


@api_view(['GET'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def current_user_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    serializer = CurrentUserSerializer(request.user, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_profile_image(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    image = request.FILES.get('profile_image')
    if not image:
        return Response(
            {"detail": "profile_image is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile.profile_image = image
    profile.save()

    serializer = CurrentUserSerializer(request.user, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([HasAPIKey])
@authentication_classes([])  # API key only for this specific endpoint
def signin(request):
    # Retrieve credentials from the request body
    identifier = request.data.get("identifier")
    password = request.data.get("password")

    if not identifier or not password:
        return Response(
            {"detail": "Both 'identifier' (email or user_id) and 'password' are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Search for user by either email OR user_id
    user = User.objects.filter(Q(email=identifier) | Q(user_id=identifier)).first()

    # Verify user exists and password is correct
    if user is None or not user.check_password(password):
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Ensure the account hasn't been disabled
    if not user.is_active:
        return Response(
            {"detail": "User account is disabled."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Generate the session token using your custom model's class method
    token = SessionToken.create_for_user(user)

    # Return the token to the client
    return Response(
        {
            "message": "Authentication successful.",
            "session_token": token.key,
            "expires_at": token.expires_at,
            "user": {
                "user_id": user.user_id,
                "email": user.email
            }
        },
        status=status.HTTP_200_OK
    )
