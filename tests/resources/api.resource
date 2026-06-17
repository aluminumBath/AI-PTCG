*** Settings ***
Documentation    Shared keywords for exercising the TCG Arena backend API.
Library          RequestsLibrary
Library          Collections
Library          String


*** Variables ***
${BASE_URL}        %{TCG_BASE_URL=http://localhost:8000}
${ADMIN_USER}      admin
${ADMIN_EMAIL}     steeleschauer@gmail.com
${ADMIN_PASS}      tmppassword


*** Keywords ***
Connect To API
    [Documentation]    Open a reusable session and confirm the backend is live.
    Create Session    tcg    ${BASE_URL}    verify=${True}
    ${r}=    GET On Session    tcg    /api/health
    Should Be True    ${r.json()}[ok]

Auth Headers
    [Arguments]    ${token}
    ${h}=    Create Dictionary    Authorization=Bearer ${token}
    RETURN    ${h}

Login
    [Arguments]    ${id}    ${password}    ${expected}=200
    ${body}=    Create Dictionary    username_or_email=${id}    password=${password}
    ${r}=    POST On Session    tcg    /api/auth/login    json=${body}
    ...    expected_status=${expected}
    RETURN    ${r}

Login As Admin
    [Documentation]    Returns a bearer token for the seeded admin account.
    ${r}=    Login    ${ADMIN_USER}    ${ADMIN_PASS}
    RETURN    ${r.json()}[token]

Register Random User
    [Documentation]    Creates a fresh non-admin account; returns its token + username.
    ${suffix}=    Generate Random String    8    [LOWER][NUMBERS]
    ${username}=    Set Variable    user_${suffix}
    ${email}=    Set Variable    ${username}@example.com
    ${body}=    Create Dictionary    username=${username}    email=${email}    password=pw_${suffix}
    ${r}=    POST On Session    tcg    /api/auth/register    json=${body}    expected_status=200
    RETURN    ${r.json()}[token]    ${username}

New AI Game
    [Arguments]    ${agent_a}=heuristic    ${agent_b}=heuristic    ${deck_a}=charizard_ex    ${deck_b}=gardevoir_ex
    ${body}=    Create Dictionary    mode=ai_vs_ai    agent_a=${agent_a}    agent_b=${agent_b}
    ...    deck_a=${deck_a}    deck_b=${deck_b}
    ${r}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    RETURN    ${r.json()}[game_id]

New Human Game
    [Arguments]    ${agent_b}=heuristic
    ${body}=    Create Dictionary    mode=human_vs_ai    human_seat=${0}    agent_b=${agent_b}
    ${r}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    RETURN    ${r.json()}

Step AI Game
    [Arguments]    ${gid}
    ${r}=    POST On Session    tcg    /api/game/${gid}/step    expected_status=200
    RETURN    ${r.json()}

Play AI Game To End
    [Documentation]    Steps an AI-vs-AI game until it finishes (or a safety cap).
    [Arguments]    ${gid}    ${max_steps}=400
    FOR    ${i}    IN RANGE    ${max_steps}
        ${r}=    Step AI Game    ${gid}
        IF    ${r}[done]    RETURN    ${r}
    END
    RETURN    ${r}
