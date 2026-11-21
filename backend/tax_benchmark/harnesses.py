from importlib.metadata import PackageNotFoundError, version

CREWAI_VERSION = '1.15.44'


def available_harnesses():
    try:
        installed = version('crewai')
    except PackageNotFoundError:
        installed = None
    return [
        {'id': 'direct', 'name': 'Direct agent', 'available': True,
         'description': 'Shared JSON-action agent loop; fresh state per trial.'},
        {'id': 'crewai', 'name': 'CrewAI', 'available': installed == CREWAI_VERSION,
         'description': 'Single agent; memory, delegation, caching and planning disabled.',
         'version': installed, 'required_version': CREWAI_VERSION},
    ]


def harness_manifest(harness, max_steps):
    if harness == 'direct':
        return {'id': 'direct', 'framework': 'builtin', 'max_model_calls': max_steps,
                'cross_trial_memory': False}
    from .crewai_harness import HARNESS_SETTINGS
    return {'id': 'crewai', 'framework': 'crewai', 'version': version('crewai'),
            'max_model_calls': max_steps, 'settings': dict(HARNESS_SETTINGS)}
