import { 
  LayoutDashboard, FolderOpen, Zap, Library, Archive, Search, Bell, Menu, CheckCircle2, CircleDashed, TriangleAlert, AlertCircle, Clock, Activity, Settings, Plus, FileText, Bot
} from 'lucide-react';
import './Dashboard.css';

export default function Dashboard() {
  return (
    <div className="dashboard-container">
      {/* SIDEBAR */}
      <aside className="dashboard-sidebar">
        <div className="sidebar-header">
          <div className="logo-bento">Bento</div>
          <div className="sidebar-version">WORKSPACE V2.4</div>
        </div>

        <nav className="sidebar-nav">
          <a href="#" className="nav-item active">
            <LayoutDashboard size={20} />
            <span>Workspace</span>
          </a>
          <a href="#" className="nav-item">
            <FolderOpen size={20} />
            <span>Collections</span>
          </a>
          <a href="#" className="nav-item">
            <Zap size={20} />
            <span>Intelligence</span>
          </a>
          <a href="#" className="nav-item">
            <Library size={20} />
            <span>Library</span>
          </a>
          <a href="#" className="nav-item">
            <Archive size={20} />
            <span>Archive</span>
          </a>
        </nav>

        <div className="sidebar-footer">
          <div className="focus-mode-toggle">
            <div className="status-dot"></div>
            <span>Focused Mode</span>
            <button className="adjust-focus-btn">Adjust Focus</button>
          </div>
          <a href="#" className="nav-item">
            <Settings size={20} />
            <span>Settings</span>
          </a>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className="dashboard-main">
        {/* TOPBAR */}
        <header className="dashboard-topbar">
          <div className="search-bar">
            <Search size={18} className="search-icon" />
            <input type="text" placeholder="Search workspace..." />
          </div>
          <div className="topbar-actions">
            <button className="icon-btn">
              <Bell size={20} />
              <span className="badge"></span>
            </button>
            <button className="ai-chef-btn">
              <Bot size={18} />
              <span>AI Chef</span>
            </button>
            <div className="user-avatar">
              <img src="https://i.pravatar.cc/150?img=32" alt="User" />
            </div>
          </div>
        </header>

        {/* HERO GREETING */}
        <section className="dashboard-hero">
          <h1 className="hero-greeting">
            Good Morning, Shakshi <span className="wave">👋</span>
          </h1>
          <p className="hero-subtitle">
            Your Bento is prepared for today. You have <span className="highlight-text">4 main courses</span> and a few light tasks.
          </p>
        </section>

        {/* BENTO GRID */}
        <section className="bento-grid">
          
          {/* COLUMN 1 */}
          <div className="bento-col col-span-2">
            
            {/* ROW 1 */}
            <div className="bento-row grid-2-col">
              {/* CARD: Workspace Health / Focus */}
              <div className="bento-card span-1">
                <div className="card-header">
                  <div className="card-icon"><TriangleAlert size={16} /></div>
                  <span className="card-label">PROJECTS</span>
                </div>
                <h2 className="card-title-lg mt-2">Design Sprint</h2>
                <div className="card-footer mt-4">
                  <div className="avatar-group">
                    <div className="avatar bg-blue-100"></div>
                    <div className="avatar bg-gray-200"></div>
                    <div className="avatar bg-orange-100 text-orange-600 text-xs flex items-center justify-center font-bold">+3</div>
                  </div>
                </div>
              </div>

              {/* CARD: AI Daily Brief / Tasks */}
              <div className="bento-card span-1">
                <div className="card-header">
                  <div className="card-icon"><CheckCircle2 size={16} /></div>
                  <span className="card-label">TODAY'S TASKS</span>
                </div>
                <ul className="task-list mt-3">
                  <li className="task-item">
                    <CheckCircle2 size={16} className="text-orange-500" />
                    <span>Review branding guidelines</span>
                  </li>
                  <li className="task-item">
                    <CircleDashed size={16} className="text-gray-400" />
                    <span>Update prototype interactions</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* ROW 2 */}
            <div className="bento-row grid-3-col mt-4">
              {/* CARD: Quick Note */}
              <div className="bento-card span-1">
                <div className="card-icon mb-2"><Menu size={16} className="text-orange-500" /></div>
                <h3 className="card-title-md">Quick Note</h3>
                <p className="card-text-sm mt-1">Don't forget the bento grid spacing should be exactly 24px...</p>
              </div>

              {/* CARD: Resources */}
              <div className="bento-card span-1">
                <div className="card-icon mb-2"><FileText size={16} className="text-orange-500" /></div>
                <h3 className="card-title-md">Resources</h3>
                <div className="resource-badge mt-2">
                  <div className="blue-dot"></div> PDF • 12MB
                </div>
              </div>

              {/* CARD: AI Prep */}
              <div className="bento-card ai-prep-card span-1">
                <div className="card-icon mb-2"><Bot size={24} className="text-white" /></div>
                <h3 className="card-title-md text-white">AI Prep</h3>
                <button className="ready-btn mt-4">Ready Workspace</button>
              </div>
            </div>
          </div>

          {/* COLUMN 2 */}
          <div className="bento-col col-span-1">
            {/* CARD: Focus Recommendation (Progress Ring) */}
            <div className="bento-card h-full flex-col-center">
              <span className="card-label mb-6 text-orange-500 font-bold">CURRENT FOCUS</span>
              
              <div className="progress-ring-container">
                <svg className="progress-ring" viewBox="0 0 120 120">
                  <circle className="ring-bg" cx="60" cy="60" r="54" />
                  <circle className="ring-fill" cx="60" cy="60" r="54" strokeDasharray="339.292" strokeDashoffset="84.823" />
                </svg>
                <div className="ring-content">
                  <span className="ring-percentage">75%</span>
                  <span className="ring-label">COMPLETE</span>
                </div>
              </div>

              <h2 className="card-title-xl mt-6">Mobile App UI</h2>
              <div className="collaborators mt-4">
                <div className="avatar-group">
                  <img className="avatar" src="https://i.pravatar.cc/150?img=11" alt="Collab" />
                  <img className="avatar" src="https://i.pravatar.cc/150?img=12" alt="Collab" />
                  <span className="collab-text">+2 Collaborators</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* BOTTOM SECTION */}
        <section className="bento-bottom-grid mt-6">
          
          {/* Timeline */}
          <div className="bento-card timeline-card">
            <span className="card-label mb-4 block">DAILY TIMELINE</span>
            <div className="timeline">
              <div className="timeline-item active">
                <div className="timeline-dot"></div>
                <div className="timeline-content">
                  <span className="timeline-time">09:00 AM</span>
                  <h4 className="timeline-title">Team Sync & Breakfast</h4>
                </div>
              </div>
              <div className="timeline-item">
                <div className="timeline-dot outline"></div>
                <div className="timeline-content">
                  <span className="timeline-time">11:30 AM</span>
                  <h4 className="timeline-title">Focus Work: UI Refinements</h4>
                </div>
              </div>
              <div className="timeline-item">
                <div className="timeline-dot outline"></div>
                <div className="timeline-content">
                  <span className="timeline-time">02:00 PM</span>
                  <h4 className="timeline-title">Client Presentation</h4>
                </div>
              </div>
            </div>
          </div>

          {/* AI Insights & Recommendations */}
          <div className="bento-card recommendations-card flex-1">
            <div className="recommendations-header">
              <div className="flex items-center gap-2">
                <Zap size={20} className="text-orange-500" />
                <h3 className="card-title-lg">Today's recommendations</h3>
              </div>
              <p className="card-text-sm mt-1 ml-7">Based on your focus and upcoming meetings.</p>
            </div>

            <div className="recommendations-grid mt-6">
              <div className="rec-item">
                <div className="rec-icon text-orange-500"><Zap size={14} /></div>
                <span className="rec-label">OPTIMIZATION</span>
                <p className="rec-text mt-2">Clear your afternoon notifications to finish the Design Sprint on time.</p>
              </div>
              
              <div className="rec-item">
                <div className="rec-icon text-orange-500"><Library size={14} /></div>
                <span className="rec-label">COLLABORATION</span>
                <p className="rec-text mt-2">Invite James to the 'Asset Library' so he can start the dev handover.</p>
              </div>
            </div>

            <div className="mt-6">
              <button className="primary-btn-large">Prepare My Workspace</button>
            </div>
          </div>

        </section>
      </main>
    </div>
  );
}
