import {afterEach, expect, test} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ThemeToggle, initialTheme} from '../components/ThemeToggle';
afterEach(()=>{localStorage.clear();delete document.documentElement.dataset.theme});
test('first use chooses Light without consulting the system preference',()=>{
  expect(initialTheme()).toBe('light');render(<ThemeToggle/>);
  expect(screen.getByRole('combobox',{name:'Theme'})).toHaveValue('light');
  expect(document.documentElement.dataset.theme).toBe('light');
});
test('explicit theme survives remount and keyboard operation',async()=>{
  const user=userEvent.setup();const mounted=render(<ThemeToggle/>);
  await user.tab();expect(screen.getByRole('combobox',{name:'Theme'})).toHaveFocus();
  await user.selectOptions(screen.getByRole('combobox'),'dark');
  expect(document.documentElement.dataset.theme).toBe('dark');
  expect(localStorage.getItem('peanalyzer-theme')).toBe('dark');
  mounted.unmount();render(<ThemeToggle/>);expect(screen.getByRole('combobox')).toHaveValue('dark');
  await user.selectOptions(screen.getByRole('combobox'),'light');
  expect(localStorage.getItem('peanalyzer-theme')).toBe('light');
});
test('unknown preference falls back to Light',()=>{
  localStorage.setItem('peanalyzer-theme','system');expect(initialTheme()).toBe('light');
});
