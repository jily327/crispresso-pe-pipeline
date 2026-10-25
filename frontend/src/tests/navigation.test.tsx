import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import App from '../app/App';
import pe from './fixtures/pe.json';
const calls=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('../api/client',()=>({api:calls.api,download:vi.fn(),initializeToken:vi.fn(),ViewerFailure:class extends Error{}}));

it.each(['{Enter}',' '])('keeps the active tab enabled and focused during %s loading',async(key)=>{
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve});
  calls.api.mockImplementation((path:string)=>{
    if(path==='capabilities')return Promise.resolve({package_version:'0.8.0'});
    if(path==='workspaces')return Promise.resolve([{registration_id:'registered',label:pe.label}]);
    if(path==='workspaces/open')return Promise.resolve(pe);
    return gate.then(()=>pe);
  });
  const user=userEvent.setup();render(<App/>);
  await user.click(await screen.findByRole('button',{name:'Open and verify'}));
  await waitFor(()=>expect(screen.getByRole('heading',{name:pe.label})).toHaveFocus());
  const tab=screen.getByRole('tab',{name:'Overview'});tab.focus();
  await user.keyboard(key);
  expect(tab).toBeEnabled();expect(tab).toHaveFocus();
  expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-busy','true');
  release();await waitFor(()=>expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-busy','false'));
  expect(tab).toHaveFocus();
});
