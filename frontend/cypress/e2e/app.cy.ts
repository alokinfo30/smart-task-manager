describe('Smart Task Manager E2E', () => {
  beforeEach(() => {
    // Mock Authentication
    cy.intercept('POST', '**/api/auth/login', (req) => {
      req.reply({
        statusCode: 200,
        body: { user_id: 'demo_user', name: 'Demo User', email: '', avatar: '👤' },
        headers: { 'Set-Cookie': 'stm_token=demo_user; Path=/;' }
      })
    }).as('login')
    cy.intercept('GET', '**/api/auth/me', { user_id: 'demo_user', name: 'Demo User', email: '', avatar: '👤' }).as('getMe')

    // Mock Data Endpoints to prevent 401 Unauthorized redirects
    let mockTasks: any[] = []
    cy.intercept('GET', '**/api/tasks', (req) => req.reply({ tasks: mockTasks })).as('getTasks')
    cy.intercept('POST', '**/api/tasks', (req) => {
      mockTasks.push({
        id: Date.now(),
        task: req.body.task,
        priority: req.body.priority,
        status: 'Pending',
        date: new Date().toISOString().split('T')[0],
        owner: 'demo_user',
        shared_with: ''
      })
      req.reply({ message: 'Success' })
    }).as('addTask')

    cy.intercept('GET', '**/api/archive', { content: '' }).as('getArchive')
    
    let mockExpenses: any[] = []
    cy.intercept('GET', '**/api/expenses', (req) => req.reply({ expenses: mockExpenses })).as('getExpenses')
    cy.intercept('POST', '**/api/expenses', (req) => {
      mockExpenses.push({
        id: Date.now(),
        amount: req.body.amount,
        category: req.body.category,
        description: req.body.description,
        date: req.body.date
      })
      req.reply({ message: 'Success' })
    }).as('addExpense')
    cy.intercept('GET', '**/api/expenses/recurring', { settings: [], history: {} }).as('getRecurring')
    cy.intercept('GET', '**/api/routines', { settings: [], history: {} }).as('getRoutines')
  })

  it('should display the login page and allow demo login', () => {
    cy.visit('/login')
    cy.contains('Sign In').should('be.visible')
    
    // Click the Demo Login button
    cy.contains('Login as Demo User').click()
    
    // Wait for the mocked API responses
    cy.wait('@login')
    cy.wait('@getMe')

    // Should redirect to main workspace and show greeting
    cy.url().should('eq', Cypress.config().baseUrl + '/')
    cy.contains('🤖 Smart Task Manager').should('be.visible')
    cy.contains('Demo User').should('be.visible')
  })

  it('should navigate between tabs successfully', () => {
    // Authenticate programmatically by setting the cookie
    cy.setCookie('stm_token', 'demo_user')
    cy.visit('/')
    // Wait for initial data fetches
    cy.wait('@getMe')
    cy.wait('@getTasks')
    
    // Check Tasks Tab
    cy.contains('Workspace').should('be.visible')
    cy.contains('Add New Task').should('be.visible')

    // Switch to Learning Hub
    cy.contains('Learning Hub').click()
    cy.contains('AI Learning Hub').should('be.visible')
    cy.contains('Generate Lesson').should('be.visible')

    // Switch to Expense Tracker
    cy.contains('Expense Tracker').click()
    cy.contains('Daily Total').should('be.visible')

    // Switch to Routines
    cy.contains('Routines').click()
    cy.contains('खुशी मेंटेन करने का सिस्टम').should('be.visible')

    // Switch to Profile
    cy.contains('Profile').click()
    cy.contains('Edit Profile').should('be.visible')
  })

  it('should allow adding a new task', () => {
    // Authenticate programmatically
    cy.setCookie('stm_token', 'demo_user')
    cy.visit('/')
    cy.wait('@getMe')
    cy.wait('@getTasks')
    
    const uniqueTaskName = `E2E Test Task ${Date.now()}`
    
    cy.get('input[placeholder="E.g., Review monthly budget..."]').type(uniqueTaskName)
    cy.contains('button', 'Add Task').click()
    
    // Wait for the simulated POST and subsequent GET refresh
    cy.wait('@addTask')
    cy.wait('@getTasks')

    // Verify the task appears on the Kanban board
    cy.contains(uniqueTaskName).should('be.visible')
  })

  it('should display an error alert on failed login', () => {
    // Intercept and force a 400 Bad Request response
    cy.intercept('POST', '**/api/auth/login', {
      statusCode: 400,
      body: { detail: 'Invalid credentials' }
    }).as('failedLogin')

    cy.visit('/login')
    cy.get('input[type="text"]').type('wrong_user')
    cy.get('input[type="password"]').type('123456')
    
    // Stub the window.alert to verify the message
    const stub = cy.stub()
    cy.on('window:alert', stub)

    cy.contains('button', 'Login').click()
    cy.wait('@failedLogin').then(() => {
      expect(stub.getCall(0)).to.be.calledWith('Failed to login. Please check your credentials.')
    })
  })

  it('should allow adding a new expense', () => {
    cy.setCookie('stm_token', 'demo_user')
    cy.visit('/')
    cy.wait('@getMe')
    
    cy.contains('Expense Tracker').click()
    cy.wait('@getExpenses')
    
    const uniqueExpense = `E2E Lunch ${Date.now()}`
    
    cy.get('input[placeholder="Amount ($)"]').type('42.50')
    cy.get('input[placeholder="Description..."]').type(uniqueExpense)
    cy.contains('button', 'Add Expense').click()

    cy.wait('@addExpense')
    cy.wait('@getExpenses')

    // Verify the new expense appears in the table
    cy.contains(uniqueExpense).should('be.visible')
    cy.contains('$42.50').should('be.visible')
  })
})