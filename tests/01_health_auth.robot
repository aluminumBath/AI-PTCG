*** Settings ***
Documentation    Health, authentication, and authorization for the TCG Arena API.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Health Endpoint Reports OK
    ${r}=    GET On Session    tcg    /api/health
    Should Be True    ${r.json()}[ok]

Seeded Admin Can Log In By Username
    ${r}=    Login    ${ADMIN_USER}    ${ADMIN_PASS}
    Dictionary Should Contain Key    ${r.json()}    token
    Should Be Equal    ${r.json()}[user][username]    ${ADMIN_USER}
    Should Be True    ${r.json()}[user][is_admin]

Seeded Admin Can Log In By Email
    ${r}=    Login    ${ADMIN_EMAIL}    ${ADMIN_PASS}
    Should Be Equal    ${r.json()}[user][email]    ${ADMIN_EMAIL}

Wrong Password Is Rejected
    Login    ${ADMIN_USER}    definitely-not-the-password    expected=401

Token Identifies The Current User
    ${token}=    Login As Admin
    ${headers}=    Auth Headers    ${token}
    ${r}=    GET On Session    tcg    /api/auth/me    headers=${headers}
    Should Be Equal    ${r.json()}[user][username]    ${ADMIN_USER}

Missing Token Is Unauthorized
    GET On Session    tcg    /api/auth/me    expected_status=401

New User Can Register And Is Not Admin
    ${token}    ${username}=    Register Random User
    ${headers}=    Auth Headers    ${token}
    ${r}=    GET On Session    tcg    /api/auth/me    headers=${headers}
    Should Be Equal    ${r.json()}[user][username]    ${username}
    Should Not Be True    ${r.json()}[user][is_admin]

Duplicate Registration Is Rejected
    ${token}    ${username}=    Register Random User
    ${body}=    Create Dictionary    username=${username}    email=dupe_${username}@example.com    password=whatever1
    POST On Session    tcg    /api/auth/register    json=${body}    expected_status=409

Non-Admin Cannot Reach Admin Endpoint
    ${token}    ${username}=    Register Random User
    ${headers}=    Auth Headers    ${token}
    GET On Session    tcg    /api/admin/users    headers=${headers}    expected_status=403

Admin Can List Users
    ${token}=    Login As Admin
    ${headers}=    Auth Headers    ${token}
    ${r}=    GET On Session    tcg    /api/admin/users    headers=${headers}
    Should Not Be Empty    ${r.json()}[users]
