'use client';

import React, { useState } from 'react';
import DashboardClientWrapper from '../DashboardClientWrapper';
import ChatAgent from './ChatAgent';
import LearningHub from './LearningHub';
import ExpenseTrackerClient from './ExpenseTrackerClient';
import RoutinesClient from './RoutinesClient';
import ResumeBuilderClient from './ResumeBuilderClient';
import AmbientCompanion from './AmbientCompanion';

export default function MainTabs({ session }: { session: string }) {
  const [activeTab, setActiveTab] = useState('Workspace');

  const tabs = ['Workspace', 'Learning Hub', 'Expense Tracker', 'Resume Builder', 'Routines', 'Health Monitor 🩺'];

  return (
    <div>
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: '1rem', borderBottom: '2px solid #E5E7EB', marginBottom: '2rem', overflowX: 'auto' }}>
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '0.75rem 1.5rem',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab ? '3px solid #3B82F6' : '3px solid transparent',
              color: activeTab === tab ? '#3B82F6' : '#6B7280',
              fontWeight: activeTab === tab ? 'bold' : 'normal',
              cursor: 'pointer',
              fontSize: '1rem',
              whiteSpace: 'nowrap'
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Active Tab Content */}
      <div key={activeTab} style={{ animation: 'fadeSlideIn 0.3s ease-out' }}>
        {activeTab === 'Workspace' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 450px', gap: '2rem', alignItems: 'start' }}>
            <DashboardClientWrapper session={session} />
            <ChatAgent />
          </div>
        )}

        {activeTab === 'Learning Hub' && <LearningHub />}
        
        {activeTab === 'Expense Tracker' && <ExpenseTrackerClient />}

        {activeTab === 'Routines' && <RoutinesClient />}

        {activeTab === 'Resume Builder' && <ResumeBuilderClient />}
      </div>

      {/* Keep Health Monitor constantly mounted outside the re-rendered key div */}
      <div style={{ display: activeTab === 'Health Monitor 🩺' ? 'block' : 'none', animation: activeTab === 'Health Monitor 🩺' ? 'fadeSlideIn 0.3s ease-out' : 'none' }}>
        <AmbientCompanion />
      </div>
    </div>
  );
}