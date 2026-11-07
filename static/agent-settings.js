// Agent configuration is served by the local app. No API keys enter this UI.
(() => {
    const list = () => document.getElementById('agent-settings-list');
    const auth = () => ({'X-Session-Token': window.SESSION_TOKEN});
    const providerNames = {claude: 'Claude Code', codex: 'Codex CLI', agy: 'Antigravity CLI'};

    async function loadAgents() {
        const target = list();
        if (!target) return;
        target.textContent = 'Loading agents…';
        try {
            const [modelResponse, statusResponse, rolesResponse, profilesResponse] = await Promise.all([
                fetch('/api/council/models', {headers: auth()}),
                fetch('/api/status', {headers: auth()}),
                fetch('/api/roles', {headers: auth()}),
                fetch('/api/council/profiles', {headers: auth()}),
            ]);
            if (!modelResponse.ok || !statusResponse.ok || !rolesResponse.ok || !profilesResponse.ok) throw new Error('Could not read agent status');
            const modelState = await modelResponse.json();
            const status = await statusResponse.json();
            const roles = await rolesResponse.json();
            const profiles = await profilesResponse.json();
            target.replaceChildren();
            for (const [name, agent] of Object.entries(modelState.agents)) {
                // The room can know about many optional CLIs. Show the configured
                // subscription workers first; inactive extras remain available.
                const row = document.createElement('div');
                row.className = 'agent-settings-row';
                row.dataset.agent = name;
                const title = document.createElement('div');
                title.className = 'agent-settings-title';
                const nameEl = document.createElement('strong');
                nameEl.textContent = agent.label;
                const badge = document.createElement('span');
                badge.className = status[name]?.available ? 'agent-ready' : 'agent-away';
                badge.textContent = status[name]?.available ? 'Online' : 'Offline';
                title.append(nameEl, badge);
                const meta = document.createElement('div');
                meta.className = 'agent-settings-meta';
                meta.textContent = `${providerNames[agent.provider] || agent.provider} · ${agent.mode === 'chat' ? 'Chat' : 'Code'} · ${agent.workspace}`;
                const tools = document.createElement('div');
                tools.className = 'agent-settings-tools';
                tools.textContent = `Installed locally: ${agent.tools.join(' · ')}. CLI permissions still apply.`;

                const controls = document.createElement('div');
                controls.className = 'agent-settings-controls';
                const options = modelState.options[agent.provider];
                const modelLabel = document.createElement('label');
                modelLabel.textContent = 'Model';
                let modelInput;
                if (options.models) {
                    modelInput = document.createElement('select');
                    for (const value of ['', ...options.models]) {
                        const option = document.createElement('option');
                        option.value = value;
                        option.textContent = value || 'CLI default';
                        modelInput.append(option);
                    }
                    modelInput.value = agent.model || '';
                } else {
                    modelInput = document.createElement('input');
                    modelInput.placeholder = 'CLI default / model ID';
                    modelInput.value = agent.model || '';
                    modelInput.maxLength = 80;
                }
                modelInput.setAttribute('aria-label', `${agent.label} model`);
                modelLabel.append(modelInput);
                const effortLabel = document.createElement('label');
                effortLabel.textContent = 'Effort';
                const effortInput = document.createElement('select');
                for (const value of ['', ...options.efforts]) {
                    const option = document.createElement('option');
                    option.value = value;
                    option.textContent = value || 'CLI default';
                    effortInput.append(option);
                }
                effortInput.value = agent.effort || '';
                effortInput.setAttribute('aria-label', `${agent.label} effort`);
                effortLabel.append(effortInput);
                const save = document.createElement('button');
                save.type = 'button';
                save.textContent = 'Apply';
                save.disabled = true;
                const message = document.createElement('span');
                message.className = 'agent-settings-message';
                const changed = () => {
                    save.disabled = modelInput.value === (agent.model || '') &&
                        effortInput.value === (agent.effort || '');
                    message.textContent = '';
                };
                modelInput.addEventListener('change', changed);
                modelInput.addEventListener('input', changed);
                effortInput.addEventListener('change', changed);
                save.addEventListener('click', async () => {
                    save.disabled = true;
                    message.textContent = 'Restarting…';
                    try {
                        const response = await fetch(`/api/council/models/${encodeURIComponent(name)}`, {
                            method: 'PUT',
                            headers: {...auth(), 'Content-Type': 'application/json'},
                            body: JSON.stringify({model: modelInput.value, effort: effortInput.value}),
                        });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.error || 'Could not apply settings');
                        agent.model = result.model || '';
                        agent.effort = result.effort || '';
                        message.textContent = 'Saved. Agent is restarting.';
                    } catch (error) {
                        changed();
                        message.textContent = error.message;
                    }
                });
                controls.append(modelLabel, effortLabel, save, message);
                const promptControls = document.createElement('div');
                promptControls.className = 'agent-settings-controls';
                const roleLabel = document.createElement('label');
                roleLabel.textContent = 'Role in prompts';
                const roleInput = document.createElement('input');
                roleInput.maxLength = 20;
                roleInput.value = roles[name] || '';
                roleInput.placeholder = 'e.g. Architect';
                roleInput.setAttribute('aria-label', `${agent.label} role`);
                roleLabel.append(roleInput);
                const roleSave = document.createElement('button');
                roleSave.type = 'button';
                roleSave.textContent = 'Save role';
                roleSave.disabled = true;
                roleInput.addEventListener('input', () => {roleSave.disabled = roleInput.value === (roles[name] || '');});
                roleSave.addEventListener('click', async () => {
                    roleSave.disabled = true;
                    try {
                        const response = await fetch(`/api/roles/${encodeURIComponent(name)}`, {
                            method: 'POST', headers: {...auth(), 'Content-Type': 'application/json'},
                            body: JSON.stringify({role: roleInput.value.trim()}),
                        });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.error || 'Could not save role');
                        roles[name] = result.role;
                        message.textContent = 'Role saved for the next agent request.';
                    } catch (error) {
                        roleSave.disabled = false;
                        message.textContent = error.message;
                    }
                });
                promptControls.append(roleLabel, roleSave);
                const profile = document.createElement('details');
                profile.className = 'agent-profile';
                const summary = document.createElement('summary');
                summary.textContent = 'Working instructions';
                const textarea = document.createElement('textarea');
                textarea.value = profiles[name] || '';
                textarea.maxLength = 1800;
                textarea.rows = 8;
                textarea.setAttribute('aria-label', `${agent.label} instructions`);
                const profileSave = document.createElement('button');
                profileSave.type = 'button';
                profileSave.textContent = 'Save instructions';
                profileSave.disabled = true;
                textarea.addEventListener('input', () => {
                    profileSave.disabled = textarea.value === profiles[name];
                });
                profileSave.addEventListener('click', async () => {
                    profileSave.disabled = true;
                    try {
                        const response = await fetch(`/api/council/profiles/${encodeURIComponent(name)}`, {
                            method: 'PUT', headers: {...auth(), 'Content-Type': 'application/json'},
                            body: JSON.stringify({instructions: textarea.value}),
                        });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.error || 'Could not save instructions');
                        profiles[name] = result.instructions;
                        textarea.value = result.instructions;
                        message.textContent = 'Instructions saved for the next request.';
                    } catch (error) {
                        profileSave.disabled = false;
                        message.textContent = error.message;
                    }
                });
                profile.append(summary, textarea, profileSave);
                row.append(title, meta, tools, controls, promptControls, profile);
                target.append(row);
            }
        } catch (error) {
            target.textContent = error.message;
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('agent-settings-refresh')?.addEventListener('click', loadAgents);
        document.getElementById('settings-toggle')?.addEventListener('click', () => {
            if (!document.getElementById('settings-bar')?.classList.contains('hidden')) loadAgents();
        });
    });
})();
