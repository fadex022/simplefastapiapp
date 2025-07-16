pipeline {
    agent any

    triggers {
        githubPush()
    }

    environment {
        PROJECT = "fastapi"
        REPOSITORY = "simplefastapiapp"
        IMAGE = "$PROJECT/$REPOSITORY"
        REGISTRY_HOST = "https://harbor.devgauss.com"
    }

    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['development', 'staging', 'production'],
            description: 'Target environment'
        )
        booleanParam(
            name: 'SKIP_TESTS',
            defaultValue: true,
            description: 'Skip test execution'
        )
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    // Get the last commit message
                    def lastCommitMessage = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()

                    // Get the last commit author
                    def lastCommitAuthor = sh(script: 'git log -1 --pretty=%an', returnStdout: true).trim()

                    // Define patterns for messages/authors to ignore
                    def ignoreMessagePattern = /\[skip ci\]/
                    def ignoreAuthor = 'Jenkins'

                    if (lastCommitMessage =~ ignoreMessagePattern || lastCommitAuthor == ignoreAuthor) {
                        echo "Skipping build due to ignored commit message or author."
                        // You might want to terminate the pipeline here, e.g.,
                        // currentBuild.result = 'NOT_BUILT' // Requires "Build Disabler Plugin" or similar
                        // You can also use "error('Skipping build')" to mark it as failed,
                        // or simply exit the script if you don't need further processing.
                        // A cleaner way is to use 'when' or 'options' to prevent the entire pipeline from running
                        // based on these conditions.
                    } else {
                        checkout scm // Only checkout if not to be skipped
                    }
                }
            }
        }

        stage('Set up Python') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    python3 -m pip install --upgrade pip

                    # Install Poetry
                    curl -sSL https://install.python-poetry.org | python3 -
                    export PATH="$HOME/.local/bin:$PATH"

                    # Configure Poetry to use the virtual environment
                    poetry config virtualenvs.create false

                    # Install dependencies using Poetry
                    poetry install
                '''
            }
        }

        /*
        stage('Code Quality Checks') {
            parallel {
                stage('Lint') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            export PATH="$HOME/.local/bin:$PATH"
                            poetry add --group dev flake8 black isort

                            # Run linting
                            poetry run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

                            # Check code formatting
                            poetry run black --check .

                            # Check import sorting
                            poetry run isort --check-only .
                        '''
                    }
                }

                stage('Security Scan') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            export PATH="$HOME/.local/bin:$PATH"
                            poetry add --group dev bandit safety

                            # Run security checks
                            poetry run bandit -r . -x tests/

                            # Check for known vulnerabilities
                            poetry run safety check
                        '''
                    }
                }
            }
        }
        */

        stage('Run Tests') {
            when {
                expression { return !params.SKIP_TESTS }
            }
            steps {
                sh '''
                    . venv/bin/activate
                    export PATH="$HOME/.local/bin:$PATH"

                    # Install additional test dependencies if needed
                    poetry add --group dev pytest-xdist pytest-cov

                    # Run tests with JUnit report for better visualization in Jenkins
                    poetry run pytest --junitxml=test-results.xml

                    # Run tests with coverage reporting
                    poetry run pytest \
                        --cov=. \
                        --cov-report=xml:coverage.xml \
                        --cov-report=html:htmlcov \
                        --cov-report=term \
                        --cov-fail-under=65
                '''
            }
            post {
                always {
                    // Archive test artifacts and coverage reports
                    archiveArtifacts artifacts: 'coverage.xml,htmlcov/**/*,test-results.xml', allowEmptyArchive: true

                    // Publish JUnit test results
                    junit 'test-results.xml'

                    // Publish HTML coverage report
                    publishHTML(target: [
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }

        stage('Build and Push Docker Image') {
            when {
                expression {
                    return env.CHANGE_ID == null // Skip for pull requests
                }
            }
            steps {
                script {
                    def image = docker.build("$IMAGE:${env.BUILD_ID}")
                    docker.withRegistry("$REGISTRY_HOST", 'registry-credentials-fadel') { 
                        image.push()
                        image.push('latest')
                    }
                }
            }
        }

        stage('Update Kubernetes Deployment') {
            when {
                expression {
                    return env.CHANGE_ID == null // Skip for pull requests
                }
            }
            steps {
                script {
                    // Update the image tag in the deployment.yaml file
                    sh """
                        sed -i 's|image: harbor.devgauss.com/fastapi/simplefastapiapp:.*|image: harbor.devgauss.com/fastapi/simplefastapiapp:${env.BUILD_ID}|' kubernetes/deployment.yaml
                    """

                    // Commit and push the changes
                    withCredentials([usernamePassword(credentialsId: 'fadel_github_creds', passwordVariable: 'GIT_PASSWORD', usernameVariable: 'GIT_USERNAME')]) {
                        // Configure Git
                        sh 'git config user.email "jenkins@devgauss.com"'
                        sh 'git config user.name "Jenkins"'

                        // Check if there are changes to commit
                        sh """
                            if git diff --quiet kubernetes/deployment.yaml; then
                                echo "No changes to deployment.yaml, skipping commit and push"
                                exit 0
                            fi

                            git add kubernetes/deployment.yaml
                            git commit -m "Update deployment image to ${env.BUILD_ID} [skip ci]"
                        """

                        // Get the repository URL and handle different formats
                        sh """
                            REPO_URL=\$(git config --get remote.origin.url)
                            BRANCH="${env.BRANCH_NAME}"

                            if [ "\$(echo \$REPO_URL | grep -c '^https://')" -eq 1 ]; then
                                # For HTTPS URLs
                                git push https://\$GIT_USERNAME:\$GIT_PASSWORD@\$(echo \$REPO_URL | sed 's|https://||') HEAD:\$BRANCH
                            elif [ "\$(echo \$REPO_URL | grep -c '^git@')" -eq 1 ]; then
                                # For SSH URLs, convert to HTTPS with credentials
                                DOMAIN=\$(echo \$REPO_URL | sed -E 's|git@([^:]+):.*|\\1|')
                                REPO_PATH=\$(echo \$REPO_URL | sed -E 's|git@[^:]+:(.*)|\\1|')
                                git push https://\$GIT_USERNAME:\$GIT_PASSWORD@\$DOMAIN/\$REPO_PATH HEAD:\$BRANCH
                            else
                                echo "Unsupported Git URL format"
                                exit 1
                            fi
                        """
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo 'Pipeline succeeded!'
        }
        failure {
            echo 'Pipeline failed!'
        }
    }
}
