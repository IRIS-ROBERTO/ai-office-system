from pydantic import BaseModel

class StateMachine(BaseModel):
    class State:
        INTAKE = 'intake'
        TRIAGE = 'triage'
        PLANNING = 'planning'
        REVIEW = 'review'
        DISPATCH = 'dispatch'
        EXECUTION = 'execution'
        VALIDATION = 'validation'
        ARCHIVE = 'archive'
    class Transition:
        INTAKE_TO_TRIAGE = (State.INTAKE, State.TRIAGE)
        TRIAGE_TO_PLANNING = (State.TRIAGE, State.PLANNING)
        PLANNING_TO_REVIEW = (State.PLANNING, State.REVIEW)
        REVIEW_TO_DISPATCH = (State.REVIEW, State.DISPATCH)
        DISPATCH_TO_EXECUTION = (State.DISPATCH, State.EXECUTION)
        EXECUTION_TO_VALIDATION = (State.EXECUTION, State.VALIDATION)
        VALIDATION_TO_ARCHIVE = (State.VALIDATION, State.ARCHIVE)
    class Permission:
        TRiage = 'triage'
        PLANer = 'planner'
        REVIEWer = 'reviewer'
        DISPATCHER = 'dispatcher'
        EXECutor = 'executor'
        AUDitor = 'auditor'
        COMMITter = 'committer'
        REPO_creator = 'repo_creator'